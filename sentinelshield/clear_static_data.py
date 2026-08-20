import os
import sqlite3

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT, "data", "sentinel.db")


def clear_all_static():
    if not os.path.exists(DB_PATH):
        print("Database does not exist yet.")
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    tables = [
        "watchlist",
        "sightings",
        "events",
        "alerts",
        "jobs",
        "hashes",
        "cyber",
        "evidence",
        "messages",
        "persons",
        "vehicle_detections",
    ]

    for tbl in tables:
        try:
            cur.execute(f"DELETE FROM {tbl};")
        except Exception:
            pass

    # Clear sample government registry cameras
    try:
        cur.execute("DELETE FROM cameras WHERE kind='registry' OR id LIKE 'gov-%';")
    except Exception:
        pass

    con.commit()
    con.close()
    print("All static/demo data erased successfully!")


if __name__ == "__main__":
    clear_all_static()
