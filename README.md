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
