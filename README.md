# Urban Tree Health Explorer (NYC)

NYC Street Tree Census app with pandas, pydeck, and matplotlib.

**Data loading:** By default the app downloads the official **single-file CSV export** from [NYC Open Data](https://data.cityofnewyork.us/Environment/2015-Street-Tree-Census-Tree-Data/uvpi-gqnh) (one HTTP request), then caches Parquet locally. That is much faster than the old paginated JSON API and works better on [Streamlit Community Cloud](https://share.streamlit.io).

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Python **3.12** is what Streamlit Community Cloud uses by default (`runtime.txt`). For Conda locally, see `environment.yml.example`.

## Configuration (optional)

| Environment variable | Meaning |
|---------------------|---------|
| `NYC_TREE_DATA_SOURCE` | `bulk` (default): CSV export · `api`: paginated JSON only |
| `NYC_TREE_BULK_TIMEOUT_S` | Read timeout for the CSV stream (default `900` seconds) |

In Streamlit Cloud you can set these in **App settings → Secrets** (same keys, TOML format).

## Deploy

Use [Streamlit Community Cloud](https://share.streamlit.io): main file `streamlit_app.py`, dependencies from `requirements.txt`.

Do **not** keep a root `environment.yml` in the repo if you use Cloud: it forces a slow Conda solve. This project uses **`requirements.txt` + `runtime.txt`** on Cloud; Conda is optional via `environment.yml.example` for local use only.
