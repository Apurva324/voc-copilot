# 🚀 Zomato VoC Copilot

An AI-powered Voice of Customer (VoC) analytics engine and dashboard built to process, classify, and analyze multi-channel customer feedback in real-time. **Zomato VoC Copilot** aggregates raw customer inputs—ranging from app reviews and support tickets to WhatsApp feedback—normalizes the data, detects emergent operational risk spikes, and delivers actionable, theme-based insights.

---

## ✨ Key Features

* **📥 Multi-Channel Data Ingestion:** Supports dynamic CSV/Excel file uploads containing customer reviews, support chat logs, and WhatsApp feedback.
* **⚡ Risk Velocity & Spike Detection:** Dynamically calculates feedback volume trends across configurable time buckets (Hourly, Daily, Weekly) and mathematically flags peak operational risk spikes.
* **🧠 AI-Powered VoC Pipeline:** Automatically classifies feedback into operational themes, extracts customer sentiments, and generates key insights.
* **📊 Interactive Dashboard:** Next.js & Tailwind CSS frontend providing live metric cards, real-time feedback inspection, risk velocity charts, and dynamic dataset management.
* **🔒 Secure & Dynamic Architecture:** Zero hardcoded data streams or secrets. Fully configured with environment variables (`.env`) and powered by MongoDB Atlas.

---

## 🛠️ Tech Stack

### **Backend**
* **Framework:** Python / FastAPI (Server-driven RESTful API)
* **Database:** MongoDB Atlas (Document store for normalized feedback & metrics)
* **Authentication:** JWT (JSON Web Tokens) with `python-dotenv` and `passlib`
* **Data Processing:** Pandas, NumPy, custom Python normalization scripts

### **Frontend**
* **Framework:** Next.js (React 19 / TypeScript)
* **Styling:** Tailwind CSS
* **Icons:** Lucide React

---

## 📁 Project Structure

```text
VOC-COPILOT/
├── Backend/
│   ├── Data/
│   │   ├── Mock/             # Mock/sample data files
│   │   ├── Processed/        # Normalized & output data
│   │   └── Raw/              # Uploaded customer raw files
│   ├── scripts/
│   │   ├── auth.py           # JWT generation & authentication handlers
│   │   ├── classify_feedback.py # Categorization logic
│   │   ├── extract_whatsapp.py  # WhatsApp feedback parser
│   │   ├── fetch_reviews.py     # Review scraper/fetcher logic
│   │   ├── generate_insights.py # VoC insights & key takeaways engine
│   │   ├── normalise.py         # Schema standardization script
│   │   └── vector_ingest.py     # Embeddings / vector store ingestion
│   └── server.py             # FastAPI entrypoint & API router
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx        # Root layout wrapper
│   │   ├── page.tsx          # Main VoC Copilot dashboard
│   │   └── globals.css       # Global styles & Tailwind directives
│   ├── components/           # Reusable UI components
│   └── public/               # Static assets & favicon
│
├── .env.example              # Template for environment variables
├── .gitignore                # Git exclusion rules
└── README.md                 # Project documentation

# 🚀 Getting Started

## 1. Prerequisites

Before running the project, ensure you have the following installed:

- Python **3.10+**
- Node.js **18+** and **npm** (or **Yarn**)
- MongoDB Atlas account (or a local MongoDB instance)

---

## 2. Backend Setup

### Step 1: Navigate to the Backend Directory

```bash
cd Backend
```

### Step 2: Create a Python Virtual Environment

```bash
python -m venv venv
```

#### macOS/Linux

```bash
source venv/bin/activate
```

#### Windows

```bash
venv\Scripts\activate
```

### Step 3: Install Required Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create a `.env` file in the project root or inside the `Backend/` directory using the following template:

```env
MONGO_URI=mongodb+srv://<username>:<password>@your-cluster.mongodb.net/?appName=voc-copilot
DB_NAME=voc_database
PORT=8000
HOST=127.0.0.1
JWT_SECRET=your_generated_random_secret_string
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

### Step 5: Start the FastAPI Backend Server

Run either of the following commands:

```bash
python server.py
```

or

```bash
uvicorn server:app --reload --port 8000
```

---

## 3. Frontend Setup

### Step 1: Navigate to the Frontend Directory

```bash
cd frontend
```

### Step 2: Install Dependencies

```bash
npm install
```

### Step 3: Start the Development Server

```bash
npm run dev
```

### Step 4: Access the Dashboard

Open the following URL in your browser:

```text
http://localhost:3000
```

The Voice of Customer Copilot dashboard should now be available.

---

# 🔌 Core API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| **POST** | `/api/upload` | Ingests CSV/XLSX files, normalizes raw feedback, and stores it in MongoDB. |
| **GET** | `/api/risk-velocity` | Returns dynamic feedback velocity, time buckets, and spike alerts. |
| **GET** | `/api/dashboard-metrics` | Fetches aggregate feedback volume, sentiment distribution, and risk indicators. |
| **GET** | `/api/insights` | Retrieves AI-generated themes, top customer quotes, and key takeaways. |
| **GET / DELETE** | `/api/datasets` | Lists all ingested feedback datasets or removes existing datasets. |

---

# 🛡️ Security & Privacy

- **Credentials Protection:** Database connection strings, JWT secrets, and API credentials are never committed to Git. All sensitive configuration is managed through environment variables stored in the `.env` file.
- **Git Safe:** Local uploads, virtual environments (`venv`), `node_modules`, build artifacts (`.next`), and other generated files are excluded from version control using `.gitignore`.

---

# 📝 License

This project is intended for **demonstration and portfolio purposes** only.

