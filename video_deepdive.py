"""One-off read-only investigation (owner 2026-11-15): where did the views of one MindLore video come from? Prints traffic sources, views per day, countries, devices, age/gender and the retention curve for VIDEO and, for comparison, the median of other recent videos' retention. Posts nothing, changes nothing."""
import json, os, sys, urllib.request, urllib.parse, datetime
VIDEO = os.environ.get('VIDEO_ID', '6tz6Hvcipk0'); BRAND = os.environ.get('BRAND', 'mindlore')
CID, SEC, RT = os.environ['YT_CLIENT_ID'], os.environ['YT_CLIENT_SECRET'], os.environ['YT_REFRESH_TOKEN_' + BRAND.upper()]
def tok():
    d = urllib.parse.urlencode({'client_id': CID, 'client_secret': SEC, 'refresh_token': RT, 'grant_type': 'refresh_token'}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', d), timeout=60))['access_token']
T = tok(); today = datetime.date.today()
def q(metrics, dims=None, filt=None, sort=None, vid=VIDEO, days=30):
    p = {'ids': 'channel==MINE', 'startDate': str(today - datetime.timedelta(days=days)), 'endDate': str(today), 'metrics': metrics}
    if dims: p['dimensions'] = dims
    if filt or vid: p['filters'] = filt or ('video==' + vid)
    if sort: p['sort'] = sort
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request('https://youtubeanalytics.googleapis.com/v2/reports?' + urllib.parse.urlencode(p), headers={'Authorization': 'Bearer ' + T}), timeout=60))
        return [c['name'] for c in r.get('columnHeaders', [])], r.get('rows', [])
    except Exception as e: return ['error'], [[str(e)[:200]]]
def show(title, res):
    print('\n== ' + title); h, rows = res; print(' | '.join(h))
    for r in rows[:25]: print(' | '.join(str(x) for x in r))
show('totals', q('views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,shares,subscribersGained,subscribersLost'))
show('traffic source', q('views,estimatedMinutesWatched,averageViewPercentage', 'insightTrafficSourceType', sort='-views'))
show('views per day', q('views,averageViewPercentage', 'day', sort='day'))
show('country', q('views', 'country', sort='-views'))
show('device', q('views', 'deviceType', sort='-views'))
show('age/gender', q('viewerPercentage', 'ageGroup,gender'))
show('shorts feed vs other (subscribed status)', q('views', 'subscribedStatus'))
show('retention curve (elapsed share of video -> audience watch ratio)', q('audienceWatchRatio,relativeRetentionPerformance', 'elapsedVideoTimeRatio'))
show('same channel, recent videos for comparison', q('views,averageViewPercentage', 'video', filt=None, vid=None, sort='-views', days=14))
