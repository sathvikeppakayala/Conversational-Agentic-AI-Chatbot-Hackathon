
from jinja2 import Template

def get_email_template(officer_type, data):
    templates = {
        "dot": Template("""
Respected Sir/Madam,
I am writing to request subscriber information under Section 91 of the Criminal Procedure Code, 1973, in connection with an investigation into an online fraud involving cheating and cyber deception under Section 420 of the IPC and Section 66-D of the Information Technology Act.
The mobile numbers identified are as follows:
{% for s in suspects %} 
 • {{ s }}
{% endfor %}

To aid in the investigation and enable further legal action, I kindly request you to furnish the following subscriber details for each of the listed numbers:
● SIM Holder Name
● ID Proof submitted during activation
● Registered Address
● Date of Activation
● Service Provider Name
● SIM Retailer (including name and outlet address, if available)

Warm regards,
 Inspector of Police
 Email: abcd@police.com
 Phone: 9999999999
"""),
        "bank": Template("""
Respected Sir/Madam,
This is to bring to your kind attention that during cyber surveillance and routine intelligence monitoring, a WhatsApp group has been identified that appears to be involved in a large-scale online investment fraud. The group lures unsuspecting individuals with deceptive investment opportunities and collects funds under false pretenses.
As part of the preliminary investigation, we have identified the following bank account(s) suspected to be used for receiving money from victims:

Suspected Beneficiary Account Details:
{% for s in suspects %} 
 • Account Number: {{ s }}
 • Bank Name: [Insert Bank Name]
 • IFSC Code: [Insert IFSC Code]
{% endfor %}

Request for Information under Section 91 CrPC:
You are kindly requested to provide the following details for each of the above-mentioned accounts:
1. Account Holder’s Full Name
2. Father’s Name
3. Registered Address as per KYC
4. Mobile Number linked to the account
5. Email ID linked to the account (if available)
6. Date of Account Opening
7. Mode of Account Opening (Online/Offline)
8. KYC Documents submitted (Photo ID & Address Proof)
9. Last 10 transactions carried out from the account (credit/debit with date, amount, and counterparty details, if available)

Warm regards,
 Inspector of Police
 Email: insp@gmail.com
 Phone: 9999999999
"""),
        "meta": Template("""
Respected Sir/Madam,
This is an official request under Section 91 of the Criminal Procedure Code, 1973, pertaining to an ongoing investigation into an online scam involving fraudulent activity on Meta platforms.
To aid the investigation, I request you to kindly provide the following information for the mobile numbers listed below:
{% for s in suspects %} 
{{ s }}
{% endfor %}

1. Instagram and Facebook Account Linkages
2. Account Access and Login Metadata

Please treat this request as urgent and confidential. The data may be shared securely with the undersigned via official communication channels.

Warm regards,
 Inspector of Police
 [Police Station Name / Cyber Crime Unit]
 Email: apple@gmail.com
 Phone: 9999999999
"""),
        "payments": Template("""
Respected Sir/Madam,
This communication is issued under the authority of Section 91 of the Criminal Procedure Code (CrPC), 1973, in connection with a suspected case of online financial fraud currently under preliminary inquiry.
During our cyber surveillance and intelligence operations, it has come to light that fraudulent actors have been using your payment gateway services to receive funds from victims.

Suspected Merchant / Payment Details:
{% for s in suspects %} 
 • Merchant ID / MID: {{ s }}
{% endfor %}

Information Requested:
● Registered Merchant Name
● Merchant Business Name / Description
● Mobile Number and Email ID Registered
● Date of Account Creation
● Bank Account(s) Linked to the Merchant Account
● KYC Documents Submitted

Warm regards,
 Inspector of Police
 Email: bed@gmail.com
 Phone: 9999999999
""")
    }

    # Map the field from the data to the suspects list for the template
    field_mapping = {
        "dot": "phones",
        "bank": "account_numbers",
        "meta": "socials",
        "payments": "upi_ids"
    }

    suspects = data.get(field_mapping[officer_type], [])
    template = templates.get(officer_type)
    if not template:
        return "Invalid officer type"

    return template.render(suspects=suspects)
