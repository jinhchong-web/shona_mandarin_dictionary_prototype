# Shona-Mandarin Dictionary Prototype

An end-to-end NLP dictionary system that provides cross-lingual retrieval, segmentation, and vector embeddings between Shona and Mandarin Chinese.

---

## 📌 Project Overview

This repository contains preprocessing code, segmentation methods, vector embedding pipelines, evaluation notebooks, and a web interface for searching and querying Shona-Mandarin translations.

Raw datasets and corpora used by the project are **not included in this repository**. They should be downloaded separately from their original sources as described below.

---

## 📁 Repository Structure

```text
├── Database/
│   └── mandarin_shona_dictionary_database.7z    # Shona and Mandarin database
│
├── Preprocessing/
│   ├── shona_preprocessing.ipynb                        # Shona text cleaning and normalization
│   ├── shona_segmentation_methods.ipynb                 # Segmentation algorithm experiments
│   ├── shona_embedding.ipynb                            # Vector embedding generation for Shona
│   ├── mandarin_preprocessing_v2.ipynb                  # Mandarin text tokenization & processing
│   ├── mandarin_embedding_v2.ipynb                      # Vector embedding generation for Mandarin
│   ├── shona_segmentation_boundary_evaluation.ipynb     # Evaluation of Boundaries Shona Segmented Word
│   └── shona_mandarin_evaluation.ipynb                  # Evaluation metrics and model performance
│
└── Interface/
    ├── app.py                   # Main application entry point (Streamlit / Flask)
    ├── db.py                    # Database connection & query execution
    ├── retrieval.py             # Vector similarity search and retrieval logic
    ├── segmentation.py          # Master segmentation handler
    ├── shona_segmenters.py      # Custom Shona word/morpheme segmenter implementations
    ├── flatcat_model.tar.gz     # Trained segmentation/morphological model
    ├── requirements.txt         # Python dependencies
    └── env.example              # Environment variables template
```

---

## 🖥️ Demo

<div align="center">
  <img src="Interface/assets/Screenshot1.png" alt="App Screenshot" width="700">
  <p><em>Example: Interface allow user change the retrieval dataset (3a - English gloss embedded only, 3b - English gloss + POS [Part of Speech] embedding), Shona word segmentation method, and number of result.</em></p>
</div>

<br>

<div align="center">
  <img src="Interface/assets/Screenshot2.png" alt="App Screenshot" width="700">
  <p><em>Example: Mandarin word input example.</em></p>
</div>

<br>

<div align="center">
  <img src="Interface/assets/Screenshot3.png" alt="App Screenshot" width="700">
  <p><em>Example: Shona word input example.</em></p>
</div>

<br>

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.9+
- PostgreSQL with the [pgvector](https://github.com/pgvector/pgvector) extension installed
- Git (with [Git LFS](https://git-lfs.com/) if pulling the Database folder)

### 1. Clone the repository
​```bash
git clone https://github.com/jinhchong-web/shona_mandarin_dictionary_prototype.git
cd shona_mandarin_dictionary_prototype
​```

### 2. Install dependencies
​```bash
cd Interface
pip install -r requirements.txt
​```

### 3. Set up the database
- Create a PostgreSQL database and enable the `pgvector` extension:
​```sql
CREATE EXTENSION IF NOT EXISTS vector;
​```
- Restore the database from `Database/mandarin_shona_dictionary_database.7z` (extract and import using your preferred method, e.g. `pg_restore` or `psql`).

### 4. Configure environment variables
Copy the example env file and fill in your database credentials:
​```bash
cp env.example .env
​```
Edit `.env` with your PostgreSQL connection details (host, port, database name, user, password).

### 5. Run the app
​```bash
streamlit run app.py
​```
The app will open at `http://localhost:8501`.

---

### Reproducing the preprocessing pipeline (optional)
If you want to rebuild the dataset from scratch rather than using the provided database dump:
1. Download the raw datasets listed in [Data Sources](#-data-sources) below.
2. Run the notebooks in `Preprocessing/` in order: preprocessing → segmentation methods → embedding → evaluation, for each language.

---

## 📊 Results

The system was evaluated across three components: Mandarin-side retrieval, Shona-side retrieval, and cross-lingual retrieval, plus segmentation accuracy.

### Monolingual Self-Retrieval
| Language | Top-1 / P@1 | MRR |
|----------|-------------|-----|
| Mandarin | 93.2%       | 0.98|
| Shona    | 79.4%       | 0.96|

### Cross-Lingual Retrieval
- Identical-meaning tier: >90% Top-k accuracy
- Partial-match tier: ~60% Top-k accuracy

### Shona Segmentation (evaluated on 308 held-out inflection pairs)
| Method                    | Accuracy |
|---------------------------|----------|
| FST-only                  | 96.1%    |
| Morfessor FlatCat-only    | 35.4%    |
| Hybrid (strict)           | 69.2%    |

Full evaluation methodology and additional metrics (boundary P/R/F1, Precision@k) are detailed in `Preprocessing/shona_mandarin_evaluation.ipynb` and `Preprocessing/shona_segmentation_boundary_evaluation.ipynb`.

---

## 📚 Data Sources

The datasets used to build and evaluate the prototype are not distributed with this repository. Please download them directly from their original sources.

### Shona

- **Leipzig Corpora Collection – Shona (Zimbabwe) Web Corpus, 2018, 100K**  
  Download the **Web 2018 100K** version (`sna-zw_web_2018_100K`) from:  
  https://wortschatz-leipzig.de/en/download/sna#sna-zw_web_2018_100K

- **Kaikki.org Shona Dictionary Data**  
  Shona lexical and word-form data derived from Wiktionary:  
  https://kaikki.org/dictionary/Shona/words/index.html

- **Duramazwi Dictionaries**  
  Authoritative published Duramazwi dictionary sources were used for Shona lexical definitions and validation where available.

### Mandarin Chinese

- **CC-CEDICT**  
  Mandarin Chinese-English dictionary data:  
  https://www.mdbg.net/chinese/dictionary?page=cc-cedict

- **zi-dataset**  
  Chinese character-level lexical and structural information:  
  https://github.com/secsilm/zi-dataset

- **HSK Dataset**  
  HSK vocabulary and associated information:  
  https://huggingface.co/datasets/willfliaw/hsk-dataset

- **Kaikki.org Chinese Dictionary Data**  
  Chinese lexical data derived from Wiktionary:  
  https://kaikki.org/dictionary/Chinese/index.html

### Dataset Availability

Due to dataset size, licensing, and redistribution considerations, the original dataset archives are not stored in this repository. Users wishing to reproduce the preprocessing and evaluation pipeline should obtain the datasets from the sources above before running the corresponding notebooks.
