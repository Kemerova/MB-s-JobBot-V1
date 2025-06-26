# 🎯 JobBot - Clean Project Structure

## ✅ **Final Clean Structure**

```
JobBot/
├── .env                     # Environment variables (API keys)
├── .gitignore              # Git ignore rules  
├── LICENSE                 # MIT License
├── README.md               # Complete documentation
├── config.yaml             # Job search configuration
├── dashboard_server.py     # Local web server for dashboard
├── main.py                 # Main application entry point
├── requirements.txt        # Python dependencies
├── run_jobbot.bat         # Windows one-click launcher
├── V1/                    # Core application modules
│   ├── __init__.py        # Package initialization
│   ├── analyzer.py        # AI job analysis & scoring
│   ├── config.py          # Configuration management
│   ├── dashboard.py       # Dashboard generation logic
│   ├── finder.py          # Multi-source job scraping
│   ├── models.py          # Data models (Job, Priority, etc.)
│   ├── reporting.py       # CSV/JSON report generation
│   └── utils.py           # Utility functions
├── resume/                # Resume files for AI matching
│   └── base_resume.txt    # Your resume content
└── output/                # Generated results
    ├── job_dashboard.html # Interactive web dashboard
    ├── jobs_data.json     # Job data for dashboard
    └── logs/              # Application logs
```

## 🚀 **How to Use**

### **Windows (Recommended)**
1. Double-click `run_jobbot.bat`
2. Dashboard opens automatically in browser

### **Command Line**
```bash
# Run job search
python main.py

# Start dashboard server
python dashboard_server.py
```

## 🔧 **Core Components**

### **main.py** - Application Orchestrator
- Loads configuration from `config.yaml`
- Initializes job finders and AI analyzers
- Coordinates job search across multiple sources
- Generates dashboard and reports

### **V1/finder.py** - Job Discovery
- Multi-source scraping (LinkedIn, Indeed, Adzuna)
- Rate limiting and error handling
- Job deduplication and filtering

### **V1/analyzer.py** - AI Analysis
- OpenAI GPT job scoring (0-100 scale)
- Resume-to-job matching
- Priority classification (HIGH/NORMAL/PREMIUM)
- Tailored resume bullet generation

### **V1/dashboard.py** - Web Interface
- Generates interactive HTML dashboard
- Real-time filtering and search
- Export capabilities for starred jobs

### **dashboard_server.py** - Local Server
- Serves dashboard on localhost:8080
- Auto-opens browser
- Background server management

## 📊 **Configuration Files**

### **config.yaml** - Job Preferences
```yaml
target_titles:
  - Software Engineer
  - Data Scientist
  - Product Manager

primary_locations:
  - Austin, TX

min_salary: 90000
experience_level: Senior
```

### **.env** - API Keys
```bash
OPENAI_API_KEY=your-key-here
ADZUNA_APP_ID=optional
ADZUNA_APP_KEY=optional
```

## 🎯 **Clean & Understandable**

This structure is designed to be:
- **Easy to navigate** - Clear file naming and organization
- **Simple to extend** - Modular V1 package for new features
- **Production ready** - Proper error handling and documentation
- **Beginner friendly** - One-click Windows launcher
- **GitHub showcase** - Professional structure and documentation

## 📝 **Next Steps**

1. Add your OpenAI API key to `.env`
2. Customize job preferences in `config.yaml`
3. Add your resume to `resume/base_resume.txt`
4. Run `run_jobbot.bat` to start job hunting!

**Perfect for demonstrating your software engineering skills on GitHub!** 🏆