FROM python:3.12-slim
RUN useradd -m -u 1000 user
WORKDIR /home/user/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user app/ ./app/
COPY --chown=user pipeline/ ./pipeline/
USER user
ENV DATA_DIR=/home/user/data DATA_REPO=modelpulse/model-pulse-data SITE_REPO=modelpulse/model-pulse PYTHONUNBUFFERED=1
EXPOSE 7860
CMD ["python", "-m", "app.serve"]
