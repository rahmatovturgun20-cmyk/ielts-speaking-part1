# -*- coding: utf-8 -*-
"""Send daily "practice ready" push notifications to subscribed users."""
import json
import os
import sqlite3
import datetime

from pywebpush import webpush, WebPushException

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "site.db")
CONFIG = os.path.join(BASE, "config.json")


def main():
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    priv = cfg.get("vapid_private", "")
    sub_url = (cfg.get("base_url") or "https://multilevelmocktest.uz").rstrip("/")
    if not priv:
        print("no vapid_private in config")
        return

    today = datetime.date.today().isoformat()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT s.endpoint, s.keys FROM push_subscriptions s "
        "LEFT JOIN users u ON u.id = s.user_id "
        "WHERE (u.id IS NULL OR u.last_practice IS NULL OR u.last_practice != ?)",
        (today,)).fetchall()
    conn.close()

    payload = json.dumps({
        "title": "Multilevel Mock Test",
        "body": "Your daily speaking practice is ready! 🎤",
        "url": sub_url,
    })

    sent = 0
    failed = 0
    for r in rows:
        try:
            sub = {"endpoint": r["endpoint"], "keys": json.loads(r["keys"])}
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=priv,
                vapid_claims={"sub": "mailto:admin@multilevelmocktest.uz"},
                timeout=20,
            )
            sent += 1
        except WebPushException as e:
            failed += 1
            code = None
            try:
                code = e.response.status_code
            except Exception:
                pass
            if code in (404, 410):
                try:
                    c = sqlite3.connect(DB)
                    c.execute("DELETE FROM push_subscriptions WHERE endpoint=?", (r["endpoint"],))
                    c.commit()
                    c.close()
                except Exception:
                    pass
        except Exception:
            failed += 1

    print("push reminders: sent=%d failed=%d" % (sent, failed))


if __name__ == "__main__":
    main()
