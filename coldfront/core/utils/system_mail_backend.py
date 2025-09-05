import subprocess
import logging
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

class SystemMailBackend(BaseEmailBackend):
    """
    Email backend that uses system mail command (like legacy portal)
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print("SYSTEM MAIL BACKEND INITIALIZED - Using system mail command")
        logger.info("SystemMailBackend initialized")
    
    def send_messages(self, email_messages):
        print(f"SYSTEM MAIL BACKEND: Attempting to send {len(email_messages)} messages")
        
        if not email_messages:
            return 0
            
        sent_count = 0
        for message in email_messages:
            try:
                print(f"SYSTEM MAIL: FROM={message.from_email} TO={message.to[0]}")
                
                # Use same format as legacy portal
                body = message.body.replace('"', '\\"').replace('\n', '\\n')
                subject = message.subject.replace('"', '\\"')
                
                cmd = 'echo "{}" | mail -s "{}" -r "{}" "{}"'.format(
                    body,
                    subject,
                    message.from_email,
                    message.to[0]
                )
                
                print(f"SYSTEM MAIL COMMAND: {cmd[:100]}...")
                
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode == 0:
                    sent_count += 1
                    print(f"SYSTEM MAIL SUCCESS: Email sent to {message.to[0]}")
                    logger.info(f"System mail sent successfully: {message.subject}")
                else:
                    print(f"SYSTEM MAIL FAILED: {result.stderr}")
                    logger.error(f"System mail failed: {result.stderr}")
                    
            except Exception as e:
                print(f"SYSTEM MAIL ERROR: {e}")
                logger.error(f"Error in system mail backend: {e}")
                
        print(f"SYSTEM MAIL BACKEND: Sent {sent_count}/{len(email_messages)} messages")
        return sent_count