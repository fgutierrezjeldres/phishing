import argparse
import mailbox
import os
import random
import re
import shutil
import tarfile
import tempfile
import urllib.request
from email import policy
from email.parser import BytesParser
from pathlib import Path


HAM_URLS = [
    "https://spamassassin.apache.org/old/publiccorpus/20021010_easy_ham.tar.bz2",
    "https://spamassassin.apache.org/old/publiccorpus/20021010_hard_ham.tar.bz2",
    "https://spamassassin.apache.org/old/publiccorpus/20030228_easy_ham.tar.bz2",
    "https://spamassassin.apache.org/old/publiccorpus/20030228_easy_ham_2.tar.bz2",
    "https://spamassassin.apache.org/old/publiccorpus/20030228_hard_ham.tar.bz2",
]
SPAM_URLS = [
    "https://spamassassin.apache.org/old/publiccorpus/20021010_spam.tar.bz2",
    "https://spamassassin.apache.org/old/publiccorpus/20030228_spam.tar.bz2",
    "https://spamassassin.apache.org/old/publiccorpus/20030228_spam_2.tar.bz2",
    "https://spamassassin.apache.org/old/publiccorpus/20050311_spam_2.tar.bz2",
]

URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
PHISH_KEYWORDS_RE = re.compile(
    r"\b(account|bank|paypal|verify|verification|password|login|security|update|confirm|urgent|suspend)\b",
    re.IGNORECASE,
)


def _download_and_extract(urls, workdir):
    extracted_dirs = []
    for url in urls:
        filename = os.path.basename(url)
        archive_path = os.path.join(workdir, filename)
        urllib.request.urlretrieve(url, archive_path)
        with tarfile.open(archive_path, mode="r:bz2") as tar:
            tar.extractall(path=workdir)
            top_level = tar.getmembers()[0].name.split("/")[0]
            extracted_dirs.append(os.path.join(workdir, top_level))
    return extracted_dirs


def _iter_email_files(folders):
    for folder in folders:
        for root, _, files in os.walk(folder):
            for name in files:
                full = os.path.join(root, name)
                if os.path.basename(root).lower() == "cmds":
                    continue
                yield full


def _parse_message(path):
    with open(path, "rb") as f:
        raw = f.read()
    msg = BytesParser(policy=policy.compat32).parsebytes(raw)
    return msg


def _decode_payload(payload, charset):
    if not isinstance(payload, bytes):
        return str(payload)
    for enc in (charset, "utf-8", "latin-1"):
        if not enc:
            continue
        try:
            return payload.decode(enc, errors="ignore")
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode("utf-8", errors="ignore")


def _message_text(msg):
    parts = []
    try:
        subject = msg.get("Subject", "")
        if subject:
            parts.append(str(subject))
    except Exception:
        pass

    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            if ctype not in ("text/plain", "text/html"):
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                payload = part.get_payload()
            charset = part.get_content_charset() or "utf-8"
            text = _decode_payload(payload, charset)
            parts.append(text)
    else:
        payload = msg.get_payload(decode=True)
        if payload is None:
            payload = msg.get_payload()
        charset = msg.get_content_charset() or "utf-8"
        parts.append(_decode_payload(payload, charset))
    return "\n".join(parts)


def _is_phishing_like(msg):
    text = _message_text(msg)
    has_url = URL_RE.search(text) is not None
    has_keyword = PHISH_KEYWORDS_RE.search(text) is not None
    return has_url and has_keyword


def _sample_messages(paths, limit, seed):
    rng = random.Random(seed)
    paths = list(paths)
    rng.shuffle(paths)
    selected = []
    for path in paths:
        try:
            selected.append(_parse_message(path))
        except Exception:
            continue
        if len(selected) >= limit:
            break
    return selected


def _sample_phishing_messages(paths, limit, seed):
    rng = random.Random(seed)
    paths = list(paths)
    rng.shuffle(paths)
    selected = []
    for path in paths:
        try:
            msg = _parse_message(path)
        except Exception:
            continue
        if _is_phishing_like(msg):
            selected.append(msg)
        if len(selected) >= limit:
            break
    return selected


def _append_unique_messages(dst, source):
    seen = set()
    for msg in dst:
        seen.add(msg.as_bytes())

    for msg in source:
        raw = msg.as_bytes()
        if raw in seen:
            continue
        seen.add(raw)
        dst.append(msg)


def _top_up_with_repeats(messages, target_size, seed):
    if not messages or len(messages) >= target_size:
        return
    rng = random.Random(seed)
    base = list(messages)
    while len(messages) < target_size:
        messages.append(rng.choice(base))


def _write_mbox(messages, mbox_path):
    mbox_path.parent.mkdir(parents=True, exist_ok=True)
    if mbox_path.exists():
        mbox_path.unlink()
    mbox = mailbox.mbox(str(mbox_path))
    for msg in messages:
        mbox.add(msg)
    mbox.flush()
    mbox.close()


def main():
    parser = argparse.ArgumentParser(description="Genera mbox reales desde corpora publicos.")
    parser.add_argument("--out-phishing", default="archivos/entradas/mbox/phishing/real_phishing.mbox")
    parser.add_argument("--out-nophishing", default="archivos/entradas/mbox/nophishing/real_nophishing.mbox")
    parser.add_argument("--count-phishing", type=int, default=3000)
    parser.add_argument("--count-nophishing", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out_ph = Path(args.out_phishing).resolve()
    out_np = Path(args.out_nophishing).resolve()

    workdir = tempfile.mkdtemp(prefix="phishing_corpus_")
    try:
        ham_dirs = _download_and_extract(HAM_URLS, workdir)
        spam_dirs = _download_and_extract(SPAM_URLS, workdir)

        ham_files = list(_iter_email_files(ham_dirs))
        spam_files = list(_iter_email_files(spam_dirs))

        ham_msgs = _sample_messages(ham_files, args.count_nophishing, args.seed)
        phish_msgs = _sample_phishing_messages(spam_files, args.count_phishing, args.seed)

        if len(phish_msgs) < args.count_phishing:
            # Fallback: completa con spam real aunque no cumpla filtro phishing-like.
            extra = _sample_messages(spam_files, args.count_phishing, args.seed + 100)
            _append_unique_messages(phish_msgs, extra)

        # Si no alcanza por unicidad real del corpus, completa con repeticion
        # de correos reales para mantener el tamano solicitado.
        _top_up_with_repeats(phish_msgs, args.count_phishing, args.seed + 1000)
        _top_up_with_repeats(ham_msgs, args.count_nophishing, args.seed + 2000)

        phish_msgs = phish_msgs[: args.count_phishing]
        ham_msgs = ham_msgs[: args.count_nophishing]

        _write_mbox(phish_msgs, out_ph)
        _write_mbox(ham_msgs, out_np)

        print(f"OK phishing: {len(phish_msgs)} -> {out_ph}")
        print(f"OK no_phishing: {len(ham_msgs)} -> {out_np}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
