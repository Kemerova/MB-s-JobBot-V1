# 🎯 JobBot - AI-Powered Job Hunting Assistant

**A sophisticated, automated job search and analysis platform that finds, scores, and tracks relevant opportunities using AI.**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![OpenAI](https://img.shields.io/badge/AI-OpenAI%20GPT-green.svg)](https://openai.com)
[![Mobile Responsive](https://img.shields.io/badge/mobile-responsive-brightgreen.svg)](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps)

## 🚀 V1 Features

### ⚡ **3x Faster Concurrent Scraping**
- Parallel job board searching with async/await
- Smart rate limiting and retry logic
- Command: `python main.py --concurrent`

### ✨ **Interactive Setup Wizard**
- Beautiful web-based configuration
- Live API key validation
- Visual job preference templates
- Access at: `http://localhost:8000/setup`

### 🛠️ **Smart Error Handling**
- User-friendly error messages with solutions
- Automatic retry with exponential backoff
- Progress tracking with error reporting

### 📱 **Mobile-First Dashboard**
- Touch-friendly interface (44px+ touch targets)
- Responsive design for all devices
- Optimized modals and navigation

### 📊 **Complete Application Tracking**
- Track job applications from interest to offer
- Interview scheduling and reminders
- Success analytics and metrics
- Export capabilities (CSV, JSON)

---

## 📁 Project Structure

```
JobBot/
├── .env                          # Environment variables (API keys)
├── config.yaml                  # Main configuration file
├── main.py                      # Main application entry point
├── dashboard_server.py          # Dashboard server launcher
├── requirements.txt             # Python dependencies
├── README.md                    # This documentation
├── V1/                         # Core application modules
│   ├── __init__.py             # Module initialization
│   ├── models.py               # Data models and structures
│   ├── config.py               # Configuration management
│   ├── finder.py               # Synchronous job scraping
│   ├── async_finder.py         # 🆕 Concurrent job scraping
│   ├── analyzer.py             # AI analysis and scoring
│   ├── reporting.py            # Report generation (mobile responsive)
│   ├── dashboard.py            # Dashboard API and logic
│   ├── setup_wizard.py         # 🆕 Interactive setup system
│   ├── application_tracking.py # 🆕 Job application management
│   ├── starred_jobs.py         # 🆕 Enhanced starring system
│   ├── cli_commands.py         # 🆕 Command-line interface
│   ├── error_handling.py       # 🆕 Smart error management
│   ├── utils.py                # Utility functions
│   └── templates/              # 🆕 HTML templates
│       └── setup_wizard.html   # Setup wizard interface
├── resume.txt                  # Your resume for AI matching
└── output/                     # Generated reports and data
    ├── job_dashboard.html      # Interactive web dashboard
    ├── jobs_data.json          # Job data for dashboard
    ├── job_applications.json   # 🆕 Application tracking data
    ├── starred_jobs.json       # 🆕 Starred jobs database
    └── logs/                   # Application logs
```

## ⚡ Quick Start

### **Option 1: Setup Wizard (Recommended)**
```bash
pip install -r requirements.txt
python -m V1.dashboard
# Visit http://localhost:8000/setup
```

### **Option 2: Manual Setup**
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add API keys to .env file
echo "OPENAI_API_KEY=your-key-here" > .env

# 3. Create configuration
python main.py --setup-config

# 4. Run job search
python main.py --concurrent
```

### **Option 3: Quick Search**
```bash
# Fast concurrent search with default settings
python main.py --concurrent --quick
```

## 🎯 Core Features

### **🔍 Intelligent Job Discovery**
- **Multi-Source Scraping**: LinkedIn, Indeed, Dice, ClearanceJobs, USAJobs, Adzuna
- **Concurrent Processing**: 3x faster searches with async/await
- **Smart Rate Limiting**: Adaptive delays to avoid blocking
- **Retry Logic**: Exponential backoff for failed requests

### **🤖 AI-Powered Analysis**
- **Job Scoring**: 0-100 relevance scores using OpenAI GPT
- **Resume Matching**: Tailored bullet points for each job
- **Priority Classification**: HIGH (86+), PREMIUM (86+), NORMAL (<86)
- **Skill Gap Analysis**: Identifies missing qualifications

### **📱 Professional Dashboard**
- **Mobile Responsive**: Works perfectly on all devices
- **Real-time Filtering**: Company, location, priority, remote options
- **Advanced Search**: Full-text search across all job fields
- **Progressive Disclosure**: Collapsible job details for better UX

### **📊 Application Tracking**
- **Full Lifecycle**: Track from interest → applied → interviewing → offer
- **Interview Management**: Schedule and track interview dates
- **Deadline Tracking**: Application deadlines with reminders
- **Success Analytics**: Response rates and time-to-hire metrics

### **⭐ Enhanced Job Management**
- **Smart Starring**: Add notes and track interested jobs
- **Export Options**: CSV, JSON exports for all data
- **Command Line**: Powerful CLI for power users
- **Search History**: Track and revisit previous searches

## 🛠️ Configuration

### **Environment Variables (.env)**
```bash
# Required
OPENAI_API_KEY=your-openai-api-key    # For AI analysis

# Optional
USAJOBS_API_KEY=your-usajobs-key      # For government jobs
ADZUNA_APP_ID=your-adzuna-id          # For Adzuna API
ADZUNA_APP_KEY=your-adzuna-key        # For Adzuna API
```

### **Job Preferences (config.yaml)**
```yaml
user:
  name: "Your Name"
  experience_level: "Senior"
  target_industry: "Technology"

jobs:
  target_titles:
    - "Software Engineer"
    - "Data Scientist"
    - "Product Manager"
  min_salary: 90000
  exclude_keywords: ["intern", "unpaid"]

location:
  primary_locations:
    - "San Francisco, CA"
    - "Austin, TX"
    - "Remote"
  remote_ok: true

scraping:
  enabled_sources: ["LinkedIn", "Indeed"]
  pages_per_source: 2
  concurrent_enabled: true

analysis:
  lazy_analysis: true
  score_threshold: 70
  llm_model: "gpt-3.5-turbo"
```

## 💻 Usage Examples

### **Command Line Interface**
```bash
# Basic job search
python main.py

# Fast concurrent search
python main.py --concurrent

# Quick search (1 page per source)
python main.py --quick

# Use specific job sources
python main.py --sources LinkedIn Indeed

# Application management
python main.py star --search "python developer"
python main.py list-starred
python main.py export-starred csv
python main.py starred-stats

# Configuration
python main.py --setup-config
python main.py --list-sources
```

### **Web Dashboard**
```bash
# Start dashboard server
python -m V1.dashboard

# Access features
# http://localhost:8000/          - Main dashboard
# http://localhost:8000/setup     - Setup wizard
# http://localhost:8000/api/docs  - API documentation
```

### **Application Tracking API**
```bash
# Get all applications
curl http://localhost:8000/api/applications

# Update application status
curl -X PUT http://localhost:8000/api/applications/123/status \
  -H "Content-Type: application/json" \
  -d '{"status": "applied", "notes": "Submitted via company website"}'

# Add interview
curl -X POST http://localhost:8000/api/applications/123/interview \
  -H "Content-Type: application/json" \
  -d '{"interview_date": "2025-01-15T14:00:00", "notes": "Technical interview"}'
```

## 📊 Application Status Workflow

```
🌟 INTERESTED → 📝 APPLIED → 📞 PHONE_SCREEN → 🎯 INTERVIEWING 
                     ↓              ↓              ↓
              ⏳ WAITING_RESPONSE ← ← ← ← ← ← ← ← ← ←
                     ↓
              💼 OFFER → ✅ ACCEPTED
                 ↓       ↗
              ❌ REJECTED
```

## 🔍 AI Analysis Criteria

The AI analyzer evaluates each job on multiple factors:

1. **Role Fit (30 points)**: Experience alignment with requirements
2. **Location Match (25 points)**: Geographic and remote preferences  
3. **Compensation (20 points)**: Salary competitiveness
4. **Company/Growth (15 points)**: Reputation and opportunities
5. **Requirements Match (10 points)**: Skills alignment

Results in a composite score (0-100) with detailed rationale.

## 📱 Mobile Features

- **Touch-Friendly**: 44px minimum touch targets
- **Swipe Navigation**: Gesture support for job cards
- **Responsive Layout**: Single-column on mobile
- **iOS Optimized**: Prevents zoom on form inputs
- **Progressive Disclosure**: Collapsible content sections

## 🚀 Technology Stack

### **Backend**
- **Python 3.8+**: Core application language
- **FastAPI**: Modern web framework for APIs
- **OpenAI GPT**: AI-powered job analysis
- **AsyncIO/AioHttp**: Concurrent request processing
- **BeautifulSoup4**: HTML parsing for web scraping
- **Pydantic**: Data validation and serialization

### **Frontend**
- **HTML5/CSS3**: Modern responsive design
- **Vanilla JavaScript**: No framework dependencies
- **Progressive Enhancement**: Works without JavaScript
- **Mobile-First**: Responsive design principles

### **Data**
- **JSON**: Structured data storage
- **CSV**: Export format compatibility
- **YAML**: Human-readable configuration

## 📋 System Requirements

- **Python**: 3.8 or higher
- **Memory**: 4GB RAM recommended
- **Storage**: 1GB free space
- **Network**: Internet connection required
- **API Key**: OpenAI API key for AI features

## ⚙️ Advanced Configuration

### **Concurrent Scraping Settings**
```yaml
scraping:
  max_concurrent_requests: 10
  connection_pool_size: 100
  request_timeout: 30
  retry_attempts: 3
  adaptive_rate_limiting: true
```

### **Error Handling**
```yaml
error_handling:
  user_friendly_messages: true
  auto_retry: true
  progress_tracking: true
  log_level: "INFO"
```

### **Mobile Optimization**
```yaml
dashboard:
  mobile_first: true
  touch_targets: "44px"
  progressive_disclosure: true
  offline_support: false
```

## 🔧 Troubleshooting

### **Common Issues**

**Setup Wizard Not Loading**
```bash
# Check if port 8000 is available
netstat -an | grep 8000

# Try alternative port
python -m V1.dashboard --port 8080
```

**Slow Job Searches**
```bash
# Use concurrent mode
python main.py --concurrent

# Reduce pages per source
python main.py --quick
```

**API Key Issues**
```bash
# Validate OpenAI key
python -c "import openai; print('Valid' if openai.api_key else 'Invalid')"

# Use setup wizard for validation
http://localhost:8000/setup
```

### **Performance Optimization**

1. **Enable Concurrent Mode**: Use `--concurrent` flag
2. **Reduce Scope**: Limit job sources and pages
3. **Use Lazy Analysis**: Enable in config for faster initial results
4. **Cache Results**: Results are automatically cached

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes with tests
4. Follow code style guidelines
5. Submit a pull request

### **Development Setup**
```bash
# Clone repository
git clone https://github.com/yourusername/jobbot.git
cd jobbot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # if available

# Run tests
pytest tests/
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- OpenAI for GPT API
- Job boards for providing opportunities
- Open source community for tools and libraries

---

**🎯 Built for modern job seekers who want to leverage AI and automation to find better opportunities faster.**

**⚡ V1 includes 3x faster searches, mobile-responsive design, and complete application tracking!**