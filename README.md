# Urban Tree Health Explorer (NYC)

NYC Street Tree Census app with pandas, pydeck, and matplotlib. Data comes from the [NYC Open Data](https://data.cityofnewyork.us/Environment/2015-Street-Tree-Census-Tree-Data/uvpi-gqnh) API and is cached locally as Parquet.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Python 3.11 is recommended (`runtime.txt` / `environment.yml`).

## Deploy

Use [Streamlit Community Cloud](https://share.streamlit.io): set the main file to `streamlit_app.py` and install dependencies from `requirements.txt`.
