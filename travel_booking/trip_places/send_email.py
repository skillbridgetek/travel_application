import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(sender_email, receiver_email, password, subject, body):
    # Create the email
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    # Connect to Gmail's SMTP server
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()  # Secure the connection
            server.login(sender_email, password)
            text = message.as_string()
            server.sendmail(sender_email, receiver_email, text)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == '__main__':
    # Usage
    sender_email = "your-email@gmail.com"
    receiver_email = "receiver-email@gmail.com"
    password = "your-gmail-password"  # Use an App Password if 2FA is enabled
    subject = "Subject of the Email"
    body = "This is the body of the email."

    send_email(sender_email, receiver_email, password, subject, body)
