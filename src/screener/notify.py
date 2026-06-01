"""Email notification: ranked shortlist in the body, full CSV attached.

Highlights new entrants vs. the prior run. Also used for failure + heartbeat
("0 results") alerts so a silent break can't quietly kill the daily consistency.

SMTP creds come from env (GMAIL_USER, GMAIL_APP_PASSWORD); never from config.
If creds are absent the message is logged and written to disk instead of sent,
so local/test runs don't fail.
"""
from __future__ import annotations

import logging
import os
import smtplib
from datetime import date
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

from .config import Config
from .schema import StockRecord

log = logging.getLogger("screener.notify")


def _fmt_pct(x, nd=0):
    return "n/a" if x is None else f"{x*100:.{nd}f}%"


def build_body(records: list[StockRecord], run_date: str) -> str:
    new = [r for r in records if r.is_new_entrant]
    lines = [
        f"# Deep-Value Screen — {run_date}",
        "",
        f"{len(records)} names passed. {len(new)} new vs. prior run.",
        "Research/idea-generation only — not investment advice. You make the call.",
        "",
        "## Ranked shortlist",
        "",
        "| # | Ticker | Region | %offATH | %>52wLow | Qual | Upside(base) | NetDebt/EBITDA | Conf | Note |",
        "|--:|--------|--------|--------:|---------:|-----:|-------------:|---------------:|-----:|------|",
    ]
    for r in records:
        star = " 🆕" if r.is_new_entrant else ""
        approx = "~" if r.ath_is_approx else ""
        note = r.prior_decision or ""
        lines.append(
            f"| {r.rank} | {r.ticker}{star} | {r.region} | "
            f"{approx}{r.pct_off_ath}% | {r.pct_above_52w_low}% | "
            f"{r.quality_score} | {_fmt_pct(r.upside_base)} | "
            f"{r.net_debt_to_ebitda if r.net_debt_to_ebitda is not None else 'n/a'} | "
            f"{r.data_confidence} | {note} |"
        )
    lines += ["", "## Write-ups", ""]
    for r in records:
        lines.append(r.writeup)
        lines.append("\n---\n")
    return "\n".join(lines)


def _send(subject: str, body: str, cfg: Config,
          attachments: Optional[list[Path]] = None) -> bool:
    user = os.environ.get("GMAIL_USER")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    recipients = cfg.email.get("recipients", [])

    if not (user and pw and recipients):
        # Degrade gracefully: persist the message so nothing is lost.
        out = Path("data/results") / f"email_{date.today().isoformat()}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f"Subject: {subject}\n\n{body}")
        log.warning("SMTP creds/recipients missing — wrote email to %s instead", out)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)
    for path in attachments or []:
        if path and Path(path).exists():
            data = Path(path).read_bytes()
            msg.add_attachment(data, maintype="text", subtype="csv",
                               filename=Path(path).name)
    try:
        with smtplib.SMTP(cfg.email.get("smtp_host", "smtp.gmail.com"),
                          cfg.email.get("smtp_port", 587)) as s:
            s.starttls()
            s.login(user, pw)
            s.send_message(msg)
        log.info("sent '%s' to %s", subject, recipients)
        return True
    except Exception as e:  # pragma: no cover - network
        log.error("email send failed: %s", e)
        return False


def send_results(records: list[StockRecord], cfg: Config, csv_path: Path,
                 run_date: Optional[str] = None,
                 calibration: Optional[str] = None) -> bool:
    run_date = run_date or date.today().isoformat()
    body = build_body(records, run_date)
    if calibration:
        body += "\n\n" + calibration
    n_new = sum(r.is_new_entrant for r in records)
    subject = f"[Deep-Value] {run_date}: {len(records)} names ({n_new} new)"
    return _send(subject, body, cfg, attachments=[csv_path])


def send_heartbeat(cfg: Config, run_date: Optional[str] = None) -> bool:
    """Email even on 0 results so a silent break is visible."""
    run_date = run_date or date.today().isoformat()
    body = (f"Deep-Value screen ran {run_date} and surfaced 0 names.\n"
            "This is a heartbeat so you know the job is alive. If you see this "
            "many days running, check thresholds in config.yaml or data sources.")
    return _send(f"[Deep-Value] {run_date}: 0 results (heartbeat)", body, cfg)


def send_failure(cfg: Config, error: str, run_date: Optional[str] = None) -> bool:
    run_date = run_date or date.today().isoformat()
    body = (f"Deep-Value screen FAILED on {run_date}.\n\n{error}\n\n"
            "GitHub Actions does not alert on failed scheduled runs — this email is "
            "the alert. Check the workflow logs.")
    return _send(f"[Deep-Value] {run_date}: RUN FAILED", body, cfg)
