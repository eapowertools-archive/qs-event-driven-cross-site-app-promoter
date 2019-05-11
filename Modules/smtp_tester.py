import smtplib


def send_test_email(
    smtp, smtp_port, sender_address, password, destination_address, subject, body
):
    message = """From: %s\nTo: %s\nSubject: %s\n\n%s""" % (
        sender_address,
        ", ".join([destination_address]),
        subject,
        body,
    )

    try:
        server = smtplib.SMTP(smtp, smtp_port)
        server.ehlo()
        server.starttls()
        server.login(sender_address, password)
        server.sendmail(sender_address, destination_address, message)
        server.close()
        return "200"
    except Exception as error:
        return "There was an error trying to send the email: '{}'".format(error)
