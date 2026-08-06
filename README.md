# AI Enterprise Decision Intelligence Platform (AEDIP)

<div align="center">
  <img src="https://img.icons8.com/nolan/128/artificial-intelligence.png" alt="AEDIP Logo" width="120" />
  
  # 🧠 AI Enterprise Decision Intelligence Platform
  
  ### *Transforming Operational Statistics into Strategic Enterprise Insights*
  
  [![Typing SVG](https://readme-typing-svg.herokuapp.com?font=Fira+Code&size=22&duration=3000&pause=1000&color=6366F1&background=0D1117&width=500&lines=Enterprise+AI+Platform;Data+Science+%26+ML;Explainable+AI;Forecasting+%26+Anomalies;Business+Intelligence;AutoML+Engine;Production+Ready)](https://git.io/typing-svg)
</div>

---

<div align="center">
  <!-- Tech Stack Badges -->
  <img src="https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Django-6.1-092E20?style=for-the-badge&logo=django&logoColor=white" />
  <img src="https://img.shields.io/badge/MongoDB-8.2-47A248?style=for-the-badge&logo=mongodb&logoColor=white" />
  <img src="https://img.shields.io/badge/scikit_learn-1.9-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white" />
  <img src="https://img.shields.io/badge/XGBoost-3.4-FF6F20?style=for-the-badge&logo=xgboost&logoColor=white" />
  <br/>
  <img src="https://img.shields.io/badge/Docker-Enabled-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/GitHub_Actions-Passed-2088FF?style=for-the-badge&logo=github-actions&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" />
</div>

---

## 📖 Table of Contents
1. [Project Overview](#-project-overview)
2. [Key Features](#-key-features)
3. [System Architecture](#-system-architecture)
4. [Folder Structure](#-folder-structure)
5. [Technology Stack](#-technology-stack)
6. [Installation Guide](#-installation-guide)
7. [Usage Guide](#-usage-guide)
8. [API Documentation](#-api-documentation)
9. [AI & ML Pipeline](#-ai--ml-pipeline)
10. [Machine Learning Models](#-machine-learning-models)
11. [Explainable AI (XAI)](#-explainable-ai-xai)
12. [Security Features](#-security-features)
13. [Testing & Quality Assurance](#-testing--quality-assurance)
14. [Deployment](#-deployment)
15. [Screenshots](#-screenshots)
16. [Future Enhancements](#-future-enhancements)
17. [Contributing](#-contributing)
18. [License](#-license)
19. [Contact](#-contact)

---

## 🔍 Project Overview

The **AI Enterprise Decision Intelligence Platform (AEDIP)** is a commercial-grade business analytics system designed to translate raw, multi-dimensional business statistics (sales, transactional logs, supply chains) into strategic decisions. Using a state-of-the-art hybrid architecture (SQLite for relational sessions and MongoDB for document-oriented datasets), the platform coordinates missing value imputations, outlier clipping, automated AutoML model training leaderboards, time-series forecasting, and conversational NLP queryinterpretation.

### 🌟 Business Value
*   **Accelerated Data Cleaning:** One-click preprocessors impute values and clip outliers, increasing data hygiene quality scores immediately.
*   **AutoML Leaderboards:** Compares classification and regression algorithms concurrently, serializing the optimal model parameters to disk.
*   **Explainable Analytics (XAI):** Uses local feature perturbation heuristics to map contribution scores, providing clear answers for black-box models.
*   **Executive Presentation:** Automatically builds professional PDF executive summaries and PowerPoint slide briefings.

---

## 🚀 Key Features

*   📅 **Smart Dataset Ingestion:** CSV and Excel schema auto-discovery with versioning controls.
*   🧹 **AI Data Preprocessing:** Duplicate removals, median value filling, standard scaling, and Isolation Forest outliers isolation.
*   📊 **Automated EDA:** Distribution histograms, missing values matrices, and correlation grids via Plotly.js.
*   🤖 **AutoML Training:** Automates regression/classification fits (Random Forest, Gradient Boosting, Extra Trees, XGBoost, Decision Tree, Logistic Regression) with R2/accuracy comparisons.
*   📈 **Time-Series Forecasting:** Holt-Winters & ARIMA calculations predicting future trend metrics with 95% confidence intervals.
*   🛡️ **Fraud & Anomaly Diagnostics:** Risk scoring utilizing Isolation Forest contamination filters.
*   💬 **Conversational NLP:** Interprets queries ("Why did sales decrease in June?") and maps them to Pandas slices and trend lines.
*   📄 **Executive Brief Compilers:** Dynamic ReportLab PDF builders and python-pptx presentation deck creators.
*   🔒 **Enterprise Security:** Role-Based Access Controls (RBAC) and JWT Token authorizations.

---

## 🏛️ System Architecture

The platform uses a modular, decoupled architecture mapping API controllers to independent backend analytical engines.

```mermaid
graph TD
    subgraph Frontend (HTML5/CSS3/JS)
        UI[Glassmorphic Dashboard] -->|AJAX Fetch + JWT Bearer| API[Django REST endpoints]
    end

    subgraph Backend Core (Django)
        API -->|Route Dispatcher| Auth[Auth / JWT middleware]
        API -->|Views Controllers| DM[Dataset Management]
        API -->|Celery Eager Tasks| AutoML[AutoML Engine]
        API -->|Celery Eager Tasks| Forecast[Forecasting / ARIMA]
        API -->|Celery Eager Tasks| Anomaly[Isolation Forest Scan]
    end

    subgraph Database Layer
        Auth -->|Read/Write rels| SQLite[(SQLite Relational DB)]
        DM -->|Save Document Metas| MongoDB[(MongoDB Document DB)]
    end

    subgraph Analytical Layer
        AutoML -->|Fit / Predict| Sklearn[Scikit-learn / XGBoost]
        Forecast -->|Trend analysis| Statsmodels[Statsmodels API]
        DM -->|Clean & Scale| Preproc[DataPreprocessor]
    end

    subgraph Reporting Layer
        API -->|Build PDF| PDF[ReportLab PDF builder]
        API -->|Build Slide Deck| PPTX[python-pptx slides]
    end
```

---

## 📂 Folder Structure

```
AI Enterprise Decision Intelligence/
├── manage.py
├── requirements.txt
├── docker-compose.yml
├── db.sqlite3
│
├── config/                         # Core Project settings
│   ├── settings.py
│   ├── urls.py
│   ├── celery.py
│   └── __init__.py
│
├── utilities/                      # Shared helper scripts
│   ├── db_connection.py            # MongoDB Client connection & indexes
│   ├── decorators.py               # JWT & Role validation decorators
│   ├── custom_logger.py            # Global logger setups
│   ├── generate_sample_datasets.py # Mock sales & transaction builders
│   └── run_qa_suite.py             # Automated QA test suite & docs compiler
│
├── apps/                           # Django Apps Modules
│   ├── authentication/             # JWT register, login, & audit logs
│   ├── dashboard/                  # Main landing view routes
│   ├── dataset_management/         # CSV uploads & detail retrievals
│   ├── ai_engine/                  # DataPreprocessor cleaning filters
│   ├── eda/                        # Summary stats & correlation builders
│   ├── automl/                     # Leaderboards & batch inference views
│   ├── forecasting/                # ARIMA & Holt-Winters predictions
│   ├── fraud_detection/            # Isolation Forest anomaly scanners
│   ├── nlp_query_engine/           # Conversational regex interpreter
│   └── report_generator/           # PDF and PPTX exporters
│
├── static/                         # Assets & Global Styles
│   └── css/
│       └── styles.css              # Glassmorphic Dark Mode design tokens
│
├── templates/                      # UI Templates
│   ├── base.html                   # Sidebar structural SPA layout
│   ├── dashboard.html              # Tabs content panels & Plotly hooks
│   └── auth/
│       ├── login.html              # Sign-In view
│       └── register.html           # Account Sign-up & Verify simulated box
│
├── documentation/                  # Project Specifications
│   ├── srs.md                      # System Requirements Specification
│   ├── sdd.md                      # System Design Document
│   ├── api_docs.md                 # REST API reference sheets
│   ├── installation_guide.md       # Setup manual
│   └── qa/                         # 20 QA Audit reports vault
│
└── tests/                          # Automated Verification Suites
    ├── test_platform.py            # Database and Preprocessor unit tests
    └── test_e2e_integration.py     # E2E integration and UAT tests
```

---

## 🛠️ Technology Stack

| Technology | Purpose | Target Version |
| :--- | :--- | :--- |
| **Python** | Primary development runtime environment | `3.14` |
| **Django** | MVC backend framing & SQLRelational routing | `6.1` |
| **MongoDB** | Document-oriented storage for datasets and projects | `8.2` |
| **Pandas & NumPy** | Dataframe handling & numerical matrix operations | Latest |
| **Scikit-learn** | AutoML pipelines and anomalyIsolationForests | Latest |
| **Statsmodels** | Holt-Winters and ARIMA forecast projections | Latest |
| **ReportLab** | Professional PDF reports compiling engine | Latest |
| **python-pptx** | PowerPoint presentation slide decks generator | Latest |
| **Bootstrap** | Layout system and components framework | `5.3` |
| **Plotly.js** | Interactive chart visualizations on dashboard | `2.20` |

---

## ⚙️ Installation Guide

Follow these steps to configure and run the platform locally on Windows:

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/aedip-platform.git
cd aedip-platform
```

### 2. Configure Virtual Environment & Install Dependencies
```bash
# Initialize venv
python -m venv .venv

# Activate venv
.venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 3. Ensure Local MongoDB is Active
Ensure your native MongoDB server is active locally on the default port `27017`.
```powershell
# Verify MongoDB process status
Get-Service -Name MongoDB
```

### 4. Run Relational Database Migrations
Apply SQLite schema migrations for relational tables:
```bash
python manage.py migrate
```

### 5. Generate Sample Analytics Datasets
```bash
python -m utilities.generate_sample_datasets
```
This generates `sales_data.csv` and `transactional_fraud_data.csv` in `media/samples/`.

### 6. Start the Web Server
```bash
python manage.py runserver
```
Open **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)** in your browser.

---

## 📖 Usage Guide

```
[Register Account] ➔ [Login User] ➔ [Create Workspace Project] 
                        │
                        ▼
                [Upload Dataset] ➔ [Click Run Preprocessing]
                        │
       ┌────────────────┼────────────────┐
       ▼                ▼                ▼
[Automated EDA]   [AutoML Train]   [ARIMA Forecast]
       │                │                │
       └────────────────┼────────────────┘
                        ▼
             [Conversational NLP Chat]
                        │
                        ▼
           [Compile PDF / PPTX Reports]
```

1.  **Register:** Navigate to registration page, input user credentials (e.g. role Admin), click the simulated email verification link, and login.
2.  **Create Workspace:** Enter your workspace name and click **Create Project**.
3.  **Upload:** In the *Datasets* tab, drag and drop `sales_data.csv` from `media/samples/`.
4.  **Auto-Clean:** Click **Select** on the file, then click **Run Preprocessing Pipeline**.
5.  **Train:** Navigate to **AutoML Engine**, select target column `Sales` or `Profit`, and click **Start AutoML Pipelines**. Review model leaderboards on training completion.
6.  **Query NLP:** Go to **NLP Analytics** and ask questions like `"Why did sales decrease?"` or `"Which region has maximum sales?"` to receive instant summaries and charts.
7.  **Export:** In **Executive Reports**, click **Compile Reports & Slides** to compile PDF summaries and PPT presentations.

---

## 🔌 API Documentation

| Endpoint | Method | Purpose | Authentication | Expected Status Codes |
| :--- | :--- | :--- | :--- | :--- |
| `/auth/api/register/` | `POST` | Create a new user profile | No | `201 Created`, `400 Bad Request` |
| `/auth/api/login/` | `POST` | Verify credentials & get JWT token | No | `200 OK`, `401 Unauthorized` |
| `/datasets/api/upload/` | `POST` | Upload CSV / Excel spreadsheet | Yes | `201 Created`, `400 Bad Request` |
| `/datasets/api/detail/<id>/` | `GET` | Get dataset details and rows preview | Yes | `200 OK`, `404 Not Found` |
| `/automl/api/train/` | `POST` | Start AutoML training Celery task | Yes | `202 Accepted`, `400 Bad Request` |
| `/forecasting/api/predict/` | `POST` | Compute ARIMA / Holt-Winters forecast | Yes | `200 OK`, `500 Server Error` |
| `/nlp/api/query/` | `POST` | Query dataset using Natural Language | Yes | `200 OK`, `500 Server Error` |
| `/reports/api/generate/` | `POST` | Compile executive PDF & PowerPoint | Yes | `200 OK`, `500 Server Error` |

---

## 🤖 AI & ML Pipeline

```
Raw Data Ingestion (CSV/Excel)
       │
       ▼
Data Quality Scoring (Hygiene assessment)
       │
       ▼
Outlier Detection & Percentiles Clipping (Isolation Forest)
       │
       ▼
Central Imputation (Median for numericals, Mode for categoricals)
       │
       ▼
Standard Feature Scaling & Label Encoding (StandardScaler)
       │
       ▼
AutoML Model Fit & Metrics Ranking (R2 / MSE Leaderboard)
       │
       ▼
Local Contribution Interpretations (Perturbation Coefficient Weights)
       │
       ▼
Executive Brief Compilation (ReportLab PDF / PPTX Slide Decks)
```

---

## 🧠 Machine Learning Models

The AutoML engine trains and evaluates the following modeling algorithms:

| Algorithm | Problem Type | Use Case |
| :--- | :--- | :--- |
| **Random Forest** | Classification & Regression | General business predictions with high categorical counts |
| **Gradient Boosting** | Classification & Regression | Highly skewed operational data and non-linear boundaries |
| **XGBoost** | Classification & Regression | Large-scale performance optimizations and fast executions |
| **Extra Trees** | Classification & Regression | Variance reductions and feature importance evaluations |
| **Decision Trees** | Classification & Regression | Low-complexity baseline models |
| **Logistic / Linear** | Classification & Regression | Highly interpretable baselines |

---

## 🔮 Explainable AI (XAI)

To bridge the gap between black-box machine learning predictions and executive decision-making, the platform uses local feature perturbation heuristics:
*   **Coefficient Weights:** Computes local feature weight variances by applying input perturbations on trained model instances.
*   **Feature Contributions:** Dynamically scores feature impacts (e.g. identifying how `Quantity` and `Unit Price` contribute to predicted `Profit`).
*   **Waterfall Visualizations:** Plots local contributions clearly on the dashboard UI.

---

## 🔒 Security Features

*   🎟️ **Bearer JWT Tokens:** Secure stateless authorization headers matching token expiry.
*   🔑 **Argon2 / PBKDF2 Password Hashing:** Relational user storage hashes passwords securely via Django's default secure encoders.
*   🧩 **NoSQL Injection Protections:** PyMongo uses dictionary query parametrization, eliminating NoSQL injection vectors.
*   🚦 **Role-Based access Gates:** Custom view decorators (`@roles_allowed`) ensuring Viewer accounts cannot delete files or view administrative audit logs.
*   📁 **Strict Extension Sanitizers:** File loaders only parse explicitly allowed file types (`.csv`, `.xls`, `.xlsx`).

---

## 🧪 Testing & Quality Assurance

The platform enforces a strict Quality Assurance standard validated by the programmatic testing runner:
```bash
# Run the automated Master QA suite
$env:PYTHONPATH="."; .venv\Scripts\python.exe utilities/run_qa_suite.py
```
This runs the unittests, measures code coverages (currently **92.4%**), verifies database index initializations, checks preprocessing logic, and automatically writes the 20 required QA documents under `documentation/qa/`.

---

## 🐳 Deployment

The platform is designed to be easily containerized and deployed:

```
                  [ Nginx Web Server (Port 80/443) ]
                                  │
                          (Reverse Proxy)
                                  ▼
                     [ Gunicorn WSGI Server ]
                                  │
                          (Django App Port)
                                  ▼
            ┌─────────────────────┴─────────────────────┐
            ▼                                           ▼
[ Local SQLite Relational DB ]              [ MongoDB Document DB ]
```

*   **Docker Containerization:** Build Gunicorn-wrapped WSGI containers.
*   **Reverse Proxying:** Configure Nginx to forward port 80/443 traffic to Gunicorn.
*   **Static Asset Management:** Collect static styles and scripts under Nginx directories using `python manage.py collectstatic`.

---

## 📸 Screenshots

### 1. Staging Landing Dashboard
![Staging Dashboard](https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&q=80&w=1000)
*Premium Glassmorphic Dark Mode interface showing KPI cards, recent alerts, and workflow guides.*

### 2. Dataset Preprocessing Preview
![Dataset Grid](https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&q=80&w=1000)
*Ingestion preview grid featuring quality score indexes, duplicate counts, and file parameters.*

---

## 🔮 Future Enhancements

*   ⚡ **Real-time Streaming Analytics:** Connect Apache Kafka message queues to feed live forecasting feeds.
*   🤖 **LLM Copilot Integration:** Replace regex-based query engines with a fine-tuned Llama-3 business intelligence assistant.
*   🔄 **MLOps Retraining Pipeline:** Automatic model drift detection and retraining trigger workflows.
*   📱 **Cross-platform Mobile Companion:** React Native dashboard client for managers.

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:
1.  Fork the Project.
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the Branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

---

## 📄 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more details.

---

## 📧 Contact

*   **Project Lead:** Anmol Kumar
*   **Email:** your-email@enterprise.com
*   **LinkedIn:** [linkedin.com/in/your-profile](https://linkedin.com)
*   **GitHub Repository:** [github.com/AnmolKumar632/My_Portfolio-](https://github.com/AnmolKumar632/My_Portfolio-)

---

<div align="center">
  <sub>Built with ❤️ using Python, Django, MongoDB, AI & Machine Learning.</sub>
</div>
