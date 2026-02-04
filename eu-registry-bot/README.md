# EU Registry Bot

Automated submission bot for EU government electronic registration portals.

## Supported Countries

| Country | Portal | Status |
|---------|--------|--------|
| 🇵🇹 Portugal | gov.pt / Autenticação.gov | ✅ Implemented |
| 🇫🇷 France | Service-Public.fr | ✅ Implemented |

## Features

- 🔐 Digital certificate authentication
- 📝 Automatic form filling
- 📎 Document attachment upload
- 📅 Scheduled execution
- 📄 Receipt download
- 🔄 Retry logic with error handling
- 📊 Detailed logging

## Installation

```bash
# Clone the repository
cd eu-registry-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## Configuration

1. Copy the environment file:
```bash
cp .env.example .env
```

2. Edit `.env` with your settings:
```env
CERTIFICATE_PATH=./certificates/your_certificate.p12
CERTIFICATE_PASSWORD=your_password
```

3. Place your digital certificate in `./certificates/`

## Usage

### Submit a Single Application

```bash
python main.py submit ./data/input/application.yaml
```

### Process All Pending Applications

```bash
python main.py process-all --input-dir ./data/input
```

### Run on Schedule (Daily)

```bash
python main.py schedule --hour 9 --minute 0
```

### Create Sample Application Files

```bash
python main.py sample
```

### Validate an Application

```bash
python main.py validate ./data/input/application.yaml
```

### Check Certificate Information

```bash
python main.py cert-info --certificate ./certificates/cert.p12
```

## Application File Format

Applications can be in YAML or JSON format:

```yaml
# application.yaml
country: portugal  # or 'france'

applicant:
  name: "Juan García"
  tax_id: "12345678A"
  email: "juan@example.com"
  phone: "+34 600 123 456"
  address: "Calle Principal 123"
  postal_code: "28001"
  city: "Madrid"

installation:
  description: "Temporary structure for cultural event"
  location: "Plaza Mayor, Madrid"
  start_date: "2024-06-01"
  end_date: "2024-06-15"
  surface_area: 50.0

attachments:
  - name: "ID Document"
    file_path: "./data/input/documents/id.pdf"
    document_type: "piece_identite"
    required: true
```

## Project Structure

```
eu-registry-bot/
├── config/              # Portal configurations
├── certificates/        # Digital certificates (git-ignored)
├── src/
│   ├── core/           # Core modules (browser, certificate, scheduler)
│   ├── portals/        # Country-specific implementations
│   │   ├── portugal/
│   │   └── france/
│   ├── models/         # Data models
│   └── utils/          # Utilities
├── data/
│   ├── input/          # Application files
│   └── output/         # Results and receipts
├── logs/               # Log files
├── main.py             # Entry point
└── requirements.txt
```

## Adding a New Country

1. Create configuration in `config/new_country.yaml`
2. Create portal module in `src/portals/new_country/`
3. Implement the `BasePortal` interface
4. Register in `main.py`

## Security Notes

⚠️ **Important:**
- Never commit certificates to version control
- Store passwords securely (use environment variables)
- Review and comply with each country's terms of service

## License

MIT License
