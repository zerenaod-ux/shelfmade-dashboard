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

KEY_JOBS = ["daily-shorts","full-video","mindlore-2d","mindlore-story-short","shelfmade-story-short","doodles","doodles-full",
            "sm-scripts","ml-scripts","review-publish","review-decide","publisher","publisher-mindlore","publisher-doodles",
            "yt-publish-shelfmade","yt-publish-mindlore","yt-publish-doodles","analytics","bio-page","daily-summary"]

def check_broken(token, topic, state):
    """Ping once per failed run of an important job. Remembers failed run ids so no repeats."""
    runs = api("/actions/runs?per_page=100", token).get("workflow_runs", [])
    done = set(state.get("failed_runs", []))
    fresh = [r for r in runs if r["name"] in KEY_JOBS and r["conclusion"] == "failure" and str(r["id"]) not in done]
    if fresh:
        names = sorted({r["name"] for r in fresh})
        send(topic, "Content Engine: a job failed", "Failed: " + ", ".join(names[:6]) + ". Open the app to see the log.")
        print("broken alert", names)
    # keep only failures from the last 3 days so the list stays small
    state["failed_runs"] = sorted(done | {str(r["id"]) for r in fresh})[-200:]
    return state

def main():
    token = os.environ["GITHUB_TOKEN"]
    topic = os.environ.get("NTFY_TOPIC", "")
    if not topic:
        raise SystemExit("NTFY_TOPIC secret is missing")
    try:
        st = json.load(open(SEEN))
    except FileNotFoundError:
        st = {}
    try:
        st = check_broken(token, topic, st)
    except Exception as e:
        print("broken check skipped:", e)
    items = [i for i in api("/issues?state=open&labels=review&per_page=100", token) if "pull_request" not in i]
    now = {str(i["number"]): i["title"] for i in items}
    try:
        seen = set(st.get("seen", []))
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
    st["seen"] = sorted(now.keys(), key=int)
    json.dump(st, open(SEEN, "w"), indent=1)

if __name__ == "__main__":
    main()
