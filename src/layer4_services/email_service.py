"""Email service for briefing delivery."""

from typing import Dict, List, Optional
from src.layer1_settings import settings, logger


class EmailService:
    """Sends HTML briefings via SendGrid."""

    def __init__(self):
        """Initialize email service."""
        self.sendgrid_api_key = settings.email_settings.sendgrid_api_key
        self.from_email = settings.email_settings.from_email
        self.from_name = settings.email_settings.from_name or "News Brief"

    def send_briefing(
        self,
        to_email: str,
        subject: str,
        briefing_text: str,
        citations: List[Dict] | None = None,
        html_template: Optional[str] = None,
    ) -> bool:
        """
        Send briefing email.

        Args:
            to_email: Recipient email
            subject: Email subject
            briefing_text: Briefing content
            citations: Article citations
            html_template: Custom HTML template

        Returns:
            True if sent successfully
        """
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content
        except ImportError:
            logger.error("sendgrid package not installed")
            return False

        try:
            # Build HTML content
            html_content = html_template or self._build_default_html(
                briefing_text, citations
            )

            # Create email
            mail = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                plain_text_content=briefing_text,
                html_content=html_content,
            )

            # Send
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(mail)

            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent to {to_email}")
                return True
            else:
                logger.error(f"SendGrid error: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False

    def _build_default_html(
        self,
        briefing_text: str,
        citations: List[Dict] | None = None,
    ) -> str:
        """Build default HTML email template."""
        citations = citations or []

        citations_html = ""
        if citations:
            citations_html = "<h3>Sources</h3><ul>"
            for citation in citations[:5]:
                source = citation.get("source", "Unknown")
                citations_html += f"<li>{source}</li>"
            citations_html += "</ul>"

        html = f"""
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        .briefing {{ background: #f8f9fa; padding: 15px; border-left: 4px solid #3498db; }}
        .sources {{ margin-top: 20px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Your Daily News Brief</h1>
        <div class="briefing">
            {briefing_text}
        </div>
        <div class="sources">
            {citations_html}
        </div>
        <hr>
        <p style="font-size: 12px; color: #999;">
            This briefing was personalized based on your interests.
        </p>
    </div>
</body>
</html>
"""
        return html

    def send_test_email(self, to_email: str) -> bool:
        """Send test email to verify configuration."""
        return self.send_briefing(
            to_email=to_email,
            subject="Test Email from News Brief",
            briefing_text="This is a test email. Your briefing service is configured correctly!",
        )
