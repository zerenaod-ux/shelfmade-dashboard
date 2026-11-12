"""Phone alert: ping the owner when new videos wait for approval.
Runs from GitHub Actions. Topic comes from the NTFY_TOPIC secret (never in code)."""
import json, os, urllib.request, urllib.error

REPO = "zerenaod-ux/shelfmade-dashboard"
SEEN = "publish/ntfy-seen.json"
APP = "https://zerenaod-ux.github.io/shelfmade-dashboard/app/"

def api(path, token):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}{path}",
        headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def send(topic, title, body):
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode("utf-8"),
        headers={"Title": title, "Tags": "video_camera", "Click": APP, "Priority": "high"})
    urllib.request.urlopen(req, timeout=30).read()

def main():
    token = os.environ["GITHUB_TOKEN"]
    topic = os.environ.get("NTFY_TOPIC", "")
    if not topic:
        raise SystemExit("NTFY_TOPIC secret is missing")
    items = [i for i in api("/issues?state=open&labels=review&per_page=100", token) if "pull_request" not in i]
    now = {str(i["number"]): i["title"] for i in items}
    try:
        seen = set(json.load(open(SEEN)).get("seen", []))
        first_run = False
    except FileNotFoundError:
        seen, first_run = set(), True
    new = [n for n in now if n not in seen]
    if new and not first_run:
        titles = [now[n].replace("Review", "").strip()[:60] for n in new[:3]]
        body = f"{len(new)} video(s) waiting for your approval:\n- " + "\n- ".join(titles)
        send(topic, "Content Engine: review", body)
        print("sent", len(new))
    else:
        print("nothing new", len(now), "waiting")
    json.dump({"seen": sorted(now.keys(), key=int)}, open(SEEN, "w"), indent=1)

if __name__ == "__main__":
    main()
