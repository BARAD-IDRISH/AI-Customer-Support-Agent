# AI Customer Support Agent

An AI-powered customer support system built with Python, Flask, and Google's Gemini API. The application enables customers to track orders, verify refund eligibility, and raise support tickets through a conversational interface.

## Key Features

- **Intelligent Customer Support:** Understands customer queries and generates contextual responses using Google Gemini.
- **Order Tracking:** Retrieves order status, order details, and expected delivery dates.
- **Refund Eligibility:** Evaluates refund eligibility based on order status and the configured refund policy.
- **Automated Ticket Management:** Creates support tickets for customer issues.
- **Customer Verification:** Validates customer email addresses against order records before providing order-specific information.
- **Duplicate Request Prevention:** Uses request IDs and database-level safeguards to prevent duplicate ticket creation during retries.
- **Input Validation:** Validates incoming requests and handles invalid input.
- **Error Handling and Logging:** Records application errors and tool execution failures for troubleshooting.
- **Automated Testing:** Includes tests for support tools and AI agent behavior.

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| AI Model | Google Gemini |
| AI Integration | Google Gen AI SDK |
| Backend Framework | Flask |
| Frontend | HTML, CSS, JavaScript |
| Database | SQLite |
| Data Validation | Pydantic |
| Testing Framework | pytest |
| Environment Configuration | python-dotenv |

## Architecture

The application follows a tool-based AI architecture in which the language model interprets customer requests and invokes predefined functions to perform supported operations.

1. **User Interface:** Accepts customer queries through a web-based chat interface.
2. **Backend API:** Validates requests and forwards messages to the AI agent.
3. **AI Agent:** Interprets user intent and selects the appropriate support tool.
4. **Tool Execution Layer:** Executes order lookup, refund eligibility, or support ticket operations.
5. **Database Layer:** Retrieves order and customer information and stores support tickets.
6. **Response Generation:** Converts tool results into customer-friendly responses.

## Project Structure

```text
ai-customer-support-agent/
├── app/
│   ├── __init__.py
│   ├── agent.py
│   ├── database.py
│   ├── tools.py
│   └── web.py
├── tests/
│   ├── test_tools.py
│   └── test_agent.py
├── templates/
│   └── index.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── chat.js
├── data/
├── logs/
├── .env
├── requirements.txt
├── README.md
└── run.py
```

## Available Operations

### Order Tracking

Retrieves order information using an order ID and customer email. The system validates the supplied details before returning order-specific information.

### Refund Eligibility

Checks whether an order meets the configured refund policy, including applicable delivery status and refund-window requirements.

### Support Ticket Creation

Creates support tickets for customer issues, associates tickets with verified customer records, and supports request-ID-based duplicate prevention.

## Installation and Setup

### Prerequisites

- Python 3.10 or later
- Google Gemini API key
- Git (optional)

### 1. Clone the repository

```bash
git clone <your-github-repository-url>
cd ai-customer-support-agent
```

Alternatively, open a terminal in the existing project directory.

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

Activate the environment on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
FLASK_SECRET_KEY=your_random_secret_key
```

Replace the placeholders with your own credentials. Keep API keys and secret values private, and do not commit `.env` to version control.

### 5. Start the application

```powershell
python run.py
```

Open the application at:

http://127.0.0.1:5000

## Example Queries

- "Track order ORD1001."
- "Can I get a refund for my delivered order?"
- "My order has a delivery problem. Please create a support ticket."

The system validates customer details before processing order-specific requests.

## Testing

Run the automated test suite:

```powershell
python -m pytest -q
```

The tests cover agent behavior and support tool functionality. Test results may vary depending on the current code and test environment.

## Security and Reliability

- Environment variables are used for API credentials and application secrets.
- Customer details are validated before order-specific data is returned.
- The agent can execute only the explicitly configured support functions.
- Input validation and request-size limits help reject invalid requests.
- Database constraints help prevent duplicate ticket creation.
- Application errors are logged for troubleshooting.

**Production considerations:** Before deployment, additional measures should be implemented as appropriate, including authentication, authorization, rate limiting, monitoring, secure database management, and protection of sensitive customer information.

## Future Enhancements

- Customer authentication and role-based access control.
- Integration with external order management and CRM systems.
- Persistent conversation history.
- Human-agent escalation and live support handoff.
- Administrative dashboard for ticket management and analytics.
- Production deployment with monitoring and rate limiting.

## License

Specify a license before distributing or reusing this software publicly.
