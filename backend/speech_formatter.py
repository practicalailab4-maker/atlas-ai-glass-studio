import re
from datetime import datetime
from decimal import Decimal
from num2words import num2words


def format_for_speech(text: str) -> str:
    """Make Atlas chat answers easier for ElevenLabs to pronounce."""
        # Speak numbered list items naturally.
    def speak_list_item(match):
        number = int(match.group(1))
        return f"Item {num2words(number)}. "

    text = re.sub(
        r"(?m)^\s*(\d{1,2})\.\s+",
        speak_list_item,
        text,
    )

    # Speak invoice identifiers clearly, including hyphenated numbers.
    def speak_invoice(match):
        digits = " ".join(num2words(int(d)) for d in match.group(2))
        return f"invoice number {digits}"

    text = re.sub(
        r"\b([A-Za-z]{2,5})-(\d{4,12})\b(?!-\d)",
        speak_invoice,
        text,
    )
    # Convert USD amounts: USD 506.71 -> five hundred six dollars and seventy-one cents
    def speak_usd(match):
        amount = Decimal(match.group(1).replace(",", ""))
        dollars = int(amount)
        cents = int((amount - dollars) * 100)

        result = f"{num2words(dollars)} dollars"
        if cents:
            result += f" and {num2words(cents)} cents"

        return result

    text = re.sub(
        r"\bUSD\s+\$?([\d,]+\.\d{2})\b",
        speak_usd,
        text,
        flags=re.IGNORECASE,
    )
        # Convert amounts written as $506.71 USD.
    text = re.sub(
        r"\$([\d,]+\.\d{2})\s+USD\b",
        speak_usd,
        text,
        flags=re.IGNORECASE,
    )
        # Convert standalone dollar amounts: $506.71.
    text = re.sub(
        r"\$([\d,]+\.\d{2})\b",
        speak_usd,
        text,
    )
        # Speak amounts in total-mismatch validation messages as currency.
    def speak_total_mismatch(match):
        expected = speak_usd_amount(match.group(1))
        found = speak_usd_amount(match.group(2))
        return f"Total mismatch. Expected {expected}. Found {found}"


    def speak_usd_amount(value):
        amount = Decimal(value.replace(",", ""))
        dollars = int(amount)
        cents = int((amount - dollars) * 100)

        result = f"{num2words(dollars)} dollars"
        if cents:
            result += f" and {num2words(cents)} cents"
        return result

    text = re.sub(
        r"Total mismatch:\s*expected\s+([\d,]+\.\d{2}),\s*found\s+([\d,]+\.\d{2})",
        speak_total_mismatch,
        text,
        flags=re.IGNORECASE,
    )
    # Make common AP labels sound more natural.
    text = re.sub(r"\bInvoice Number\s*:", "Invoice", text, flags=re.IGNORECASE)
    text = re.sub(r"\bVendor\s*:", "from", text, flags=re.IGNORECASE)
    text = re.sub(r"\bInvoice Date\s*:", "issued on", text, flags=re.IGNORECASE)
    text = re.sub(r"\bDue Date\s*:", "due on", text, flags=re.IGNORECASE)
    text = re.sub(r"\bAmount\s*:", "for", text, flags=re.IGNORECASE)
    text = re.sub(r"\bStatus\s*:\s*Needs Review\b", "awaiting review", text, flags=re.IGNORECASE)
    # Pronounce abbreviated company names naturally.
    text = re.sub(
        r"\bCo\.(?=\s|$)",
        "Company",
        text,
        flags=re.IGNORECASE,
    )
    # Pronounce common business suffixes letter by letter.
    text = re.sub(
    r"\s+\bCo\.(?=\s|$|[,;:])",
    "",
    text,
    flags=re.IGNORECASE,
    )
        # Speak database record IDs clearly, digit by digit.
    def speak_record_id(match):
        digits = " ".join(num2words(int(d)) for d in match.group(1))
        return f"record I D, {digits}"

    text = re.sub(
        r"\bID\s*[:#]?\s*(\d+)\b",
        speak_record_id,
        text,
        flags=re.IGNORECASE,
    )

    # Remove awkward punctuation after spoken business suffixes.
    text = re.sub(
        r"(el el see)\s*\.(?=\s|$)",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )

    # Speak subtraction and equality naturally.
    text = re.sub(r"\s+-\s+", " minus ", text)
    text = re.sub(r"\s*=\s*", " equals ", text)
        # Use natural phrases instead of words ElevenLabs may spell out.
    text = re.sub(
        r"\bwas approved\b",
        "received approval",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\bdated\s+",
        "issued on ",
        text,
        flags=re.IGNORECASE,
    )

    # Speak mathematical operators naturally.
    text = re.sub(r"\s+-\s+", " minus ", text)
    text = re.sub(r"\s*=\s*", " equals ", text)
    return text