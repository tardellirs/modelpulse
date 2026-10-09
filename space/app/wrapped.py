"""Model Pulse Wrapped: an author's last 12 months on the Hub, computed from per-repo series, for their models or
their datasets."""
from datetime import date, timedelta

# the tables each kind reads: per-repo series, skipped days, repo metadata, per-author series
KINDS = {
    "models": {"series": "series", "skip": "skip_days", "repos": "models", "authors": "author_series"},
    "datasets": {"series": "ds_series", "skip": "ds_skip_days", "repos": "datasets", "authors": "ds_author_series"},
}


class Wrapped:
    def __init__(self, store, repos=None):
        self.s = store
        self.has_datasets = bool(repos and repos.ok)
        last = {"models": store.meta["days"][-1]}
        if self.has_datasets:
            last["datasets"] = repos.meta.get("datasets_days", [last["models"]])[-1]
        self.last = {k: date.fromisoformat(str(v)) for k, v in last.items()}
        self._ranks = {}

    def window(self, kind: str):
        last = self.last[kind]
        return last - timedelta(days=365), last

    def ranks(self, kind: str):
        """Downloads in the window for every author in the kind's author series (1K+ all-time), ranked."""
        if kind not in self._ranks:
            start, last = self.window(kind)
            rows = self.s.con().execute(
                f"""WITH a AS (SELECT author, arg_max(dl_all, day) AS v1 FROM {KINDS[kind]['authors']} WHERE day BETWEEN ? AND ? GROUP BY author),
                        b AS (SELECT author, arg_max(dl_all, day) AS v0 FROM {KINDS[kind]['authors']} WHERE day BETWEEN ? AND ? GROUP BY author)
                   SELECT a.author, greatest(0, a.v1 - coalesce(b.v0, 0)) AS yr FROM a LEFT JOIN b USING (author) ORDER BY yr DESC""",
                [last - timedelta(days=10), last, start - timedelta(days=10), start]).fetchall()
            self._ranks[kind] = [yr for _, yr in rows]
        return self._ranks[kind]

    def rank_of(self, kind: str, downloads: int):
        """Where a yearly total would sit among ranked authors (1-based)."""
        ranks = self.ranks(kind)
        lo, hi = 0, len(ranks)
        while lo < hi:  # ranks are sorted descending
            mid = (lo + hi) // 2
            if ranks[mid] > downloads:
                lo = mid + 1
            else:
                hi = mid
        return lo + 1

    def kinds(self, author: str):
        """Which kinds this author has downloads for, models first."""
        out = []
        for kind in KINDS:
            if kind == "datasets" and not self.has_datasets:
                continue
            r = self.s.con().execute(f"SELECT 1 FROM {KINDS[kind]['repos']} WHERE author = ? AND coalesce(dl_all, dl30, 0) > 0 LIMIT 1",
                                     [author]).fetchone()
            if r:
                out.append(kind)
        return out

    def find_author(self, name: str):
        for kind in KINDS:
            if kind == "datasets" and not self.has_datasets:
                continue
            r = self.s.con().execute(f"SELECT author FROM {KINDS[kind]['repos']} WHERE lower(author) = lower(?) LIMIT 1", [name]).fetchone()
            if r:
                return r[0]
        return None

    def build(self, author: str, kind: str | None = None):
        """The Wrapped of one kind; without a kind, models if the author has any, else datasets."""
        kinds = self.kinds(author)
        if kind is None:
            kind = kinds[0] if kinds else "models"
        if kind not in kinds:
            return None
        out = self._build(author, kind)
        if out:
            out["kind"], out["kinds"] = kind, kinds
        return out

    def _build(self, author: str, kind: str):
        con = self.s.con()
        t = KINDS[kind]
        start, last = self.window(kind)
        # per-repo day-over-day increments inside the window, aggregated in DuckDB (authors can own 70K+ repos);
        # repos entering tracking don't create jumps because only consecutive snapshots of the same repo count
        con.execute(
            f"""CREATE OR REPLACE TEMP TABLE w_inc AS
               WITH s AS (
                 SELECT id, day, dl_all, lag(dl_all) OVER w AS p, lag(day) OVER w AS pd
                 FROM {t['series']}
                 WHERE id IN (SELECT id FROM {t['repos']} WHERE author = ?) AND day BETWEEN ? AND ?
                   AND day NOT IN (SELECT day FROM {t['skip']})
                 WINDOW w AS (PARTITION BY id ORDER BY day))
               SELECT id, day, greatest(1, day - pd) AS gap, greatest(0, dl_all - p) AS d
               FROM s WHERE p IS NOT NULL AND day > ?""",
            [author, start - timedelta(days=10), last, start])
        by_day = con.execute("SELECT day, gap, sum(d) FROM w_inc GROUP BY day, gap").fetchall()
        top_repos = con.execute("SELECT id, sum(d) AS t FROM w_inc GROUP BY id ORDER BY t DESC LIMIT 5").fetchall()
        if not by_day:
            return None
        daily = {}
        for day, gap, d in by_day:
            gap = max(1, int(gap))
            for k in range(gap):
                dd = day - timedelta(days=k)
                if dd > start:
                    daily[dd] = daily.get(dd, 0) + d / gap
        year_dl = int(sum(daily.values()))
        if year_dl <= 0:
            return None

        weeks = {}
        for d, v in daily.items():
            monday = d - timedelta(days=d.weekday())
            weeks[monday] = weeks.get(monday, 0) + v
        last_monday = last - timedelta(days=last.weekday())
        full_weeks = {k: v for k, v in weeks.items() if k < last_monday and k > start}
        best_week = max(full_weeks.items(), key=lambda kv: kv[1]) if full_weeks else None
        months = {}
        for d, v in daily.items():
            k = d.replace(day=1)
            months[k] = months.get(k, 0) + v

        repos = con.execute(f"SELECT id, likes, created_at, pipeline_tag, dl_all FROM {t['repos']} WHERE author = ?", [author]).fetchall()
        tags = {m[0]: m[3] for m in repos}
        likes_then = dict(con.execute(
            f"SELECT id, arg_max(likes, day) FROM {t['series']} WHERE day BETWEEN ? AND ? AND id IN (SELECT id FROM {t['repos']} WHERE author = ?) GROUP BY id",
            [start - timedelta(days=10), start, author]).fetchall())
        likes_now = sum((m[1] or 0) for m in repos)
        likes_gained = max(0, likes_now - sum((v or 0) for v in likes_then.values()))
        new_repos = sum(1 for m in repos if m[2] and m[2].date() > start)

        top = top_repos[0] if top_repos else None
        ripple = self._ripple(author) if kind == "models" else self._used_by(author)

        rank = self.rank_of(kind, year_dl)
        n = len(self.ranks(kind))
        seconds = 365 * 86400
        out = {
            "author": author,
            "period": {"from": str(start + timedelta(days=1)), "to": str(last)},
            "downloads": year_dl,
            "downloads_all": int(sum((m[4] or 0) for m in repos)),  # the Hub's all-time counters, as on the author page
            "every_seconds": round(seconds / year_dl, 2),
            "per_minute": round(year_dl / (365 * 1440), 1),
            "rank": rank,
            "authors_ranked": n,
            "top_pct": round(100 * rank / n, 2) if n else None,
            "likes_gained": int(likes_gained),
            "likes_total": int(likes_now),
            "models_total": len(repos),
            "models_new": new_repos,
            "top_model": {"id": top[0], "downloads": int(top[1]), "task": tags.get(top[0]),
                          "share": round(top[1] / year_dl, 3)} if top else None,
            "top_models": [{"id": m, "downloads": int(v)} for m, v in top_repos[:5] if v > 0],
            "best_week": {"week_of": str(best_week[0]), "downloads": int(best_week[1])} if best_week else None,
            "weeks": [{"week_of": str(k), "downloads": int(v)} for k, v in sorted(full_weeks.items())],
            "months": [{"month": str(k), "downloads": int(v)} for k, v in sorted(months.items())],
            "ripple": ripple,
        }
        if kind == "datasets":
            out["tasks"] = self._tasks(author)
        return out

    def _ripple(self, author: str):
        """Models by other people that build on the author's models."""
        con = self.s.con()
        ripple = con.execute(
            """SELECT count(DISTINCT id), coalesce(sum(dl30), 0) FROM children
               WHERE parent IN (SELECT id FROM models WHERE author = ?) AND author <> ?""", [author, author]).fetchone()
        top_child = con.execute(
            """SELECT id, dl30, base_relation FROM children
               WHERE parent IN (SELECT id FROM models WHERE author = ?) AND author <> ? ORDER BY dl30 DESC NULLS LAST LIMIT 1""",
            [author, author]).fetchone()
        return {"models": int(ripple[0]), "downloads_30d": int(ripple[1]),
                "top": {"id": top_child[0], "downloads_30d": int(top_child[1] or 0), "relation": top_child[2]} if top_child else None}

    def _used_by(self, author: str):
        """Models by other people that list one of the author's datasets as training data, and Spaces that use them."""
        con = self.s.con()
        mine = "SELECT id FROM datasets WHERE author = ?"
        # one row per model, however many of the author's datasets it lists
        con.execute(
            f"""CREATE OR REPLACE TEMP TABLE w_users AS
                SELECT u.src AS id, any_value(u.dst) AS dataset, any_value(m.dl30) AS dl30 FROM uses u JOIN models m ON m.id = u.src
                WHERE u.src_kind = 'model' AND u.dst_kind = 'dataset' AND u.dst IN ({mine}) AND m.author <> ?
                GROUP BY u.src""", [author, author])
        n, dl = con.execute("SELECT count(*), coalesce(sum(dl30), 0) FROM w_users").fetchone()
        top = con.execute("SELECT id, dl30, dataset FROM w_users ORDER BY dl30 DESC NULLS LAST LIMIT 1").fetchone()
        spaces = con.execute(
            f"""SELECT count(DISTINCT u.src) FROM uses u LEFT JOIN spaces s ON s.id = u.src
                WHERE u.src_kind = 'space' AND u.dst_kind = 'dataset' AND u.dst IN ({mine}) AND coalesce(s.author, split_part(u.src, '/', 1)) <> ?""",
            [author, author]).fetchone()[0]
        return {"models": int(n), "downloads_30d": int(dl), "spaces": int(spaces),
                "top": {"id": top[0], "downloads_30d": int(top[1] or 0), "relation": "trained on", "dataset": top[2]} if top else None}

    def _tasks(self, author: str):
        """The author's dataset downloads in the last 30 days by task category, biggest first."""
        rows = self.s.con().execute(
            "SELECT pipeline_tag, sum(dl30) AS dl, count(*) AS n FROM datasets WHERE author = ? AND pipeline_tag IS NOT NULL "
            "GROUP BY 1 HAVING sum(dl30) > 0 ORDER BY dl DESC", [author]).fetchall()
        total = self.s.con().execute("SELECT coalesce(sum(dl30), 0) FROM datasets WHERE author = ?", [author]).fetchone()[0]
        return {"total_30d": int(total), "top": [{"task": r[0], "downloads_30d": int(r[1]), "datasets": int(r[2])} for r in rows[:5]]}
