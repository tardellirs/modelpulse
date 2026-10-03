"""Model Pulse Wrapped: an author's last 12 months on the Hub, computed from per-model series."""
from datetime import date, timedelta


class Wrapped:
    def __init__(self, store):
        self.s = store
        self.last = date.fromisoformat(store.meta["days"][-1])
        self.start = self.last - timedelta(days=365)
        self._ranks = None
        self._n = 0

    def ranks(self):
        """Downloads in the window for every author in author_series (1K+ all-time), ranked."""
        if self._ranks is None:
            rows = self.s.con().execute(
                """WITH a AS (SELECT author, arg_max(dl_all, day) AS v1 FROM author_series WHERE day BETWEEN ? AND ? GROUP BY author),
                        b AS (SELECT author, arg_max(dl_all, day) AS v0 FROM author_series WHERE day BETWEEN ? AND ? GROUP BY author)
                   SELECT a.author, greatest(0, a.v1 - coalesce(b.v0, 0)) AS yr FROM a LEFT JOIN b USING (author) ORDER BY yr DESC""",
                [self.last - timedelta(days=10), self.last, self.start - timedelta(days=10), self.start]).fetchall()
            self._ranks = [(a, yr) for a, yr in rows]
            self._n = len(rows)
        return self._ranks

    def rank_of(self, downloads: int):
        """Where a yearly total would sit among ranked authors (1-based)."""
        ranks = self.ranks()
        lo, hi = 0, len(ranks)
        while lo < hi:  # ranks are sorted descending
            mid = (lo + hi) // 2
            if ranks[mid][1] > downloads:
                lo = mid + 1
            else:
                hi = mid
        return lo + 1

    def find_author(self, name: str):
        r = self.s.con().execute("SELECT author FROM models WHERE lower(author) = lower(?) LIMIT 1", [name]).fetchone()
        return r[0] if r else None

    def build(self, author: str):
        con = self.s.con()
        # per-model day-over-day increments inside the window, aggregated in DuckDB (authors can own 70K+ models);
        # models entering tracking don't create jumps because only consecutive snapshots of the same model count
        con.execute(
            """CREATE OR REPLACE TEMP TABLE w_inc AS
               WITH s AS (
                 SELECT id, day, dl_all, lag(dl_all) OVER w AS p, lag(day) OVER w AS pd
                 FROM series
                 WHERE id IN (SELECT id FROM models WHERE author = ?) AND day BETWEEN ? AND ?
                 WINDOW w AS (PARTITION BY id ORDER BY day))
               SELECT id, day, greatest(1, day - pd) AS gap, greatest(0, dl_all - p) AS d
               FROM s WHERE p IS NOT NULL AND day > ?""",
            [author, self.start - timedelta(days=10), self.last, self.start])
        by_day = con.execute("SELECT day, gap, sum(d) FROM w_inc GROUP BY day, gap").fetchall()
        top_models = con.execute("SELECT id, sum(d) AS t FROM w_inc GROUP BY id ORDER BY t DESC LIMIT 5").fetchall()
        if not by_day:
            return None
        daily = {}
        for day, gap, d in by_day:
            gap = max(1, int(gap))
            for k in range(gap):
                dd = day - timedelta(days=k)
                if dd > self.start:
                    daily[dd] = daily.get(dd, 0) + d / gap
        year_dl = int(sum(daily.values()))
        if year_dl <= 0:
            return None

        weeks = {}
        for d, v in daily.items():
            monday = d - timedelta(days=d.weekday())
            weeks[monday] = weeks.get(monday, 0) + v
        last_monday = self.last - timedelta(days=self.last.weekday())
        full_weeks = {k: v for k, v in weeks.items() if k < last_monday and k > self.start}
        best_week = max(full_weeks.items(), key=lambda kv: kv[1]) if full_weeks else None
        months = {}
        for d, v in daily.items():
            k = d.replace(day=1)
            months[k] = months.get(k, 0) + v

        models = con.execute("SELECT id, likes, created_at, pipeline_tag FROM models WHERE author = ?", [author]).fetchall()
        tags = {m[0]: m[3] for m in models}
        likes_then = dict(con.execute(
            "SELECT id, arg_max(likes, day) FROM series WHERE day BETWEEN ? AND ? AND id IN (SELECT id FROM models WHERE author = ?) GROUP BY id",
            [self.start - timedelta(days=10), self.start, author]).fetchall())
        likes_now = sum((m[1] or 0) for m in models)
        likes_gained = max(0, likes_now - sum((v or 0) for v in likes_then.values()))
        new_models = sum(1 for m in models if m[2] and m[2].date() > self.start)

        top = top_models[0] if top_models else None

        ripple = con.execute(
            """SELECT count(DISTINCT id), coalesce(sum(dl30), 0) FROM children
               WHERE parent IN (SELECT id FROM models WHERE author = ?) AND author <> ?""", [author, author]).fetchone()
        top_child = con.execute(
            """SELECT id, dl30, base_relation FROM children
               WHERE parent IN (SELECT id FROM models WHERE author = ?) AND author <> ? ORDER BY dl30 DESC NULLS LAST LIMIT 1""",
            [author, author]).fetchone()

        self.ranks()
        rank = self.rank_of(year_dl)
        seconds = 365 * 86400
        return {
            "author": author,
            "period": {"from": str(self.start + timedelta(days=1)), "to": str(self.last)},
            "downloads": year_dl,
            "every_seconds": round(seconds / year_dl, 2),
            "per_minute": round(year_dl / (365 * 1440), 1),
            "rank": rank,
            "authors_ranked": self._n,
            "top_pct": round(100 * rank / self._n, 2) if self._n else None,
            "likes_gained": int(likes_gained),
            "likes_total": int(likes_now),
            "models_total": len(models),
            "models_new": new_models,
            "top_model": {"id": top[0], "downloads": int(top[1]), "task": tags.get(top[0]),
                          "share": round(top[1] / year_dl, 3)} if top else None,
            "top_models": [{"id": m, "downloads": int(v)} for m, v in top_models[:5] if v > 0],
            "best_week": {"week_of": str(best_week[0]), "downloads": int(best_week[1])} if best_week else None,
            "weeks": [{"week_of": str(k), "downloads": int(v)} for k, v in sorted(full_weeks.items())],
            "months": [{"month": str(k), "downloads": int(v)} for k, v in sorted(months.items())],
            "ripple": {"models": int(ripple[0]), "downloads_30d": int(ripple[1]),
                       "top": {"id": top_child[0], "downloads_30d": int(top_child[1] or 0), "relation": top_child[2]} if top_child else None},
        }
