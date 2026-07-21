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

🚀 Getting Started1. PrerequisitesPython 3.10+Node.js 18+ & npm/yarnMongoDB Atlas Cluster account (or local MongoDB instance)2. Backend SetupNavigate to the backend directory:Bashcd Backend
Create and activate a Python virtual environment:Bashpython -m venv venv
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
Install required packages:Bashpip install -r requirements.txt
Create a .env file in the root or Backend/ directory based on .env.example:Code snippetMONGO_URI=mongodb+srv://<username>:<password>@your-cluster.mongodb.net/?appName=voc-copilot
DB_NAME=voc_database
PORT=8000
HOST=127.0.0.1
JWT_SECRET=your_generated_random_secret_string
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
Start the backend FastAPI server:Bashpython server.py
# or
uvicorn server:app --reload --port 8000
3. Frontend SetupNavigate to the frontend directory:Bashcd frontend
Install dependencies:Bashnpm install
Start the Next.js development server:Bashnpm run dev
Open http://localhost:3000 in your browser to access the dashboard!
🔌 Core API EndpointsMethodEndpointDescriptionPOST/api/uploadIngests CSV/XLSX files, normalizes raw feedback, & stores in MongoDBGET/api/risk-velocityReturns dynamic feedback velocity, time buckets, & spike alertsGET/api/dashboard-metricsFetches aggregate volume, sentiment splits, & risk indicatorsGET/api/insightsRetrieves AI-generated themes, top customer quotes, & key takeawaysGET / DELETE/api/datasetsLists or removes ingested feedback datasets🛡️ Security & PrivacyCredentials Protection: All database connection strings, JWT keys, and API credentials are kept strictly out of Git via .env variables.Git Safe: Local uploads, node modules, build outputs (.next), and virtual environments (venv) are strictly ignored using .gitignore.📝 LicenseThis project is created for demonstration and portfolio purposes.
***

### 💡 How to add this to your GitHub repo:
1. Create a file named `README.md` in the root folder of your project (`VOC-COPILOT`).
2. Paste the content above into it and save.
3. Commit and push it:
   ```bash
   git add README.md
   git commit -m "Add comprehensive project README"
   git push origin main
