"""Build an intuitive, evidence-led, single-file Garmin dashboard."""
import html, json, math, statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parent; DATA=ROOT/'data'; OUT=ROOT/'dashboard.html'; TODAY=date.today()
def load(name,default):
    try:return json.loads((DATA/name).read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError):return default
def day(v):
    try:return datetime.strptime(str(v)[:10],'%Y-%m-%d').date()
    except (ValueError,TypeError):return None
def num(v):
    if isinstance(v,dict):v=v.get('value')
    try:
        x=float(v);return x if math.isfinite(x) else None
    except (ValueError,TypeError):return None
def avg(vals):
    x=[float(v) for v in vals if v is not None];return statistics.fmean(x) if x else None
def fmt(v,n=1,s=''):return '—' if v is None else f'{v:.{n}f}{s}'
def signed(v,n=1,s=''):return '—' if v is None else f'{v:+.{n}f}{s}'
def pace_text(v):
    if v is None:return '—'
    minutes=int(v);seconds=round((v-minutes)*60)
    if seconds==60:minutes+=1;seconds=0
    return f'{minutes}:{seconds:02d}/km'
def clamp(v):return max(0,min(100,v))
def nested(o,*keys):
    for k in keys:
        if not isinstance(o,dict):return None
        o=o.get(k)
    return o
def pearson(p):
    if len(p)<7:return None
    xs,ys=zip(*p);xm,ym=avg(xs),avg(ys);d=math.sqrt(sum((x-xm)**2 for x in xs)*sum((y-ym)**2 for y in ys))
    return sum((x-xm)*(y-ym) for x,y in p)/d if d else None
def qeffect(p):
    if len(p)<12:return None
    # Sort only by the explanatory value. Sorting full tuples would let the
    # outcome break ties (for example many zero-load days), exaggerating the
    # quartile effect we are trying to measure.
    p=sorted(p,key=lambda item:item[0]);n=max(3,len(p)//4);return avg(y for _,y in p[-n:])-avg(y for _,y in p[:n])

# Normalize Garmin records.
acts=[]
for a in load('activities.json',[]):
    d=day(a.get('startTimeLocal'))
    if not d:continue
    typ=a.get('activityType') or {}; key=(typ.get('typeKey') if isinstance(typ,dict) else str(typ)) or 'other'
    km=(num(a.get('distance')) or 0)/1000; hrs=(num(a.get('duration')) or 0)/3600; run='running' in key.lower()
    acts.append(dict(
        d=d,name=str(a.get('activityName') or key.title()),sport=key.replace('_',' ').title(),
        key=key.lower(),run=run,km=km,hrs=hrs,load=num(a.get('activityTrainingLoad')) or 0,
        elev=num(a.get('elevationGain')) or 0,pace=hrs*60/km if run and km else None,
        avg_hr=num(a.get('averageHR')),aerobic_te=num(a.get('aerobicTrainingEffect')),
        anaerobic_te=num(a.get('anaerobicTrainingEffect')),te_label=str(a.get('trainingEffectLabel') or '').replace('_',' ').title(),
        moderate=num(a.get('moderateIntensityMinutes')) or 0,vigorous=num(a.get('vigorousIntensityMinutes')) or 0,
        cadence=num(a.get('averageRunningCadenceInStepsPerMinute')),vertical_osc=num(a.get('avgVerticalOscillation')),
        ground_contact=num(a.get('avgGroundContactTime')),stride_cm=num(a.get('avgStrideLength')),
        vertical_ratio=num(a.get('avgVerticalRatio')),body_battery_impact=num(a.get('differenceBodyBattery')),
        zones=[num(a.get(f'hrTimeInZone_{i}')) or 0 for i in range(1,6)]
    ))
acts.sort(key=lambda x:x['d'])
daily={}; sleep={}; hrv={}
for x in load('daily_summaries.json',[]):
    d=day(x.get('calendarDate'))
    if d:daily[d]={
        'rhr':num(nested(x,'heartRate','restingValue')),
        'steps':num(nested(x,'movement','steps','value')),
        'step_goal':num(nested(x,'movement','steps','goal')),
        'active_calories':num(nested(x,'calories','burnedActive')),
        'total_calories':num(nested(x,'calories','burnedTotal')),
        'intensity_goal':num(nested(x,'intensityMinutes','goal')),
        'moderate':num(nested(x,'intensityMinutes','moderate')),
        'vigorous':num(nested(x,'intensityMinutes','vigorous')),
        'stress':num(nested(x,'stress','avgLevel')),
        'stress_max':num(nested(x,'stress','maxLevel')),
        'body_battery':num(nested(x,'bodyBattery','latestValue')),
        'body_battery_min':num(nested(x,'bodyBattery','minValue')),
        'body_battery_max':num(nested(x,'bodyBattery','maxValue')),
        'body_battery_charge':num(nested(x,'bodyBattery','chargedValue')),
        'body_battery_drain':num(nested(x,'bodyBattery','drainedValue')),
        'respiration':num(nested(x,'respiration','avgValue')),
        'spo2':num(nested(x,'pulseOx','avgValue')),
        'spo2_min':num(nested(x,'pulseOx','minValue')),
        'spo2_latest':num(nested(x,'pulseOx','latestValue')),
    }
for x in load('sleep.json',[]):
    d=day(x.get('calendarDate')); sec=num(x.get('sleepTimeSeconds'))
    if d and sec:sleep[d]={
        'hours':sec/3600,'deep':(num(x.get('deepSleepSeconds')) or 0)/3600,
        'rem':(num(x.get('remSleepSeconds')) or 0)/3600,
        'score':num(nested(x,'sleepScores','overall','value')),
        'score_label':str(nested(x,'sleepScores','overall','qualifierKey') or '').title(),
        'spo2':num(x.get('averageSpO2Value')),'spo2_min':num(x.get('lowestSpO2Value')),
        'respiration':num(x.get('averageRespirationValue')),'sleep_stress':num(x.get('avgSleepStress')),
        'need_min':num(nested(x,'sleepNeed','actual')),
        'start_ms':num(x.get('sleepStartTimestampLocal')),
    }
for x in load('hrv.json',[]):
    d=day(x.get('calendarDate'))
    if d:hrv[d]={
        'night':num(x.get('lastNightAvg')),'weekly':num(x.get('weeklyAvg')),
        'status':str(x.get('status') or '').replace('_',' ').title(),
        'balanced_low':num(nested(x,'baseline','balancedLow')),
        'balanced_high':num(nested(x,'baseline','balancedUpper')),
    }
weights=[]
for x in load('weight.json',[]):
    w=x.get('latestWeight') or {};d=day(x.get('summaryDate') or w.get('calendarDate'));g=num(w.get('weight'))
    if d and g:weights.append({'d':d,'kg':g/1000})
weights.sort(key=lambda x:x['d'])
fitness_age=load('fitness_age.json',{})
zones=load('heart_rate_zones.json',[])
running_zone=next((z for z in zones if isinstance(z,dict) and z.get('sport')=='RUNNING'),{})
refresh_meta=load('refresh_status.json',{})
try:
    last_refresh_dt=datetime.fromisoformat(refresh_meta.get('last_success',''))
    last_refresh_display=last_refresh_dt.strftime('%d %b %Y, %I:%M %p')
except (ValueError,TypeError):
    last_refresh_display='Not refreshed yet'

# Recent signals compared with the user's own baseline.
last7=[TODAY-timedelta(days=i) for i in range(6,-1,-1)]; base=[TODAY-timedelta(days=i) for i in range(34,6,-1)]
def window(src,key,days):return avg(src.get(d,{}).get(key) for d in days)
h7,hb=window(hrv,'night',last7),window(hrv,'night',base); r7,rb=window(daily,'rhr',last7),window(daily,'rhr',base); s7,sb=window(sleep,'hours',last7),window(sleep,'hours',base)
hd=((h7/hb)-1)*100 if h7 is not None and hb else None; rd=r7-rb if r7 is not None and rb is not None else None; sd=s7-sb if s7 is not None and sb is not None else None
parts=[]
if hd is not None:parts.append(clamp(50+hd*4))
if rd is not None:parts.append(clamp(50-rd*8))
if sd is not None:parts.append(clamp(50+sd*40))
rec=round(avg(parts)) if parts else None; rec_label='Supportive' if rec is not None and rec>=65 else 'Mixed' if rec is not None and rec>=42 else 'Strained' if rec is not None else 'Building baseline'
latest=max((a['d'] for a in acts),default=None); gap=(TODAY-latest).days if latest else None
recent=[a for a in acts if a['d'] in last7]; dist=sum(a['km'] for a in recent); load7=sum(a['load'] for a in recent)
prior=[]
for off in range(1,5):
    ds={TODAY-timedelta(days=off*7+i) for i in range(7)};g=[a for a in acts if a['d'] in ds];prior.append((sum(a['km'] for a in g),sum(a['load'] for a in g)))
typdist=avg(x for x,_ in prior) or 0; typload=avg(x for _,x in prior) or 0; ratio=load7/typload if typload else None
flags=sum([hd is not None and hd<-8,rd is not None and rd>4,sd is not None and sd<-.75])
if flags>=2: verdict,action='Protect recovery','Keep the next session easy or rest: two or more recovery markers are below your baseline.'
elif gap is not None and gap>=7: verdict,action='Rebuild consistency','The training gap is the main limiter. If you feel well, restart with an easy run and build gradually.'
elif ratio is not None and ratio>1.5: verdict,action='Absorb the work','Load is well above your recent norm. Keep intensity controlled while recovery catches up.'
elif rec is not None and rec>=60: verdict,action='Train as planned','Recovery is broadly supportive and load is within your recent pattern.'
else: verdict,action='Keep it controlled','Signals are mixed. Favor easy aerobic work and reassess tomorrow.'
coverage=min(sum(src.get(d,{}).get(k) is not None for d in last7) for src,k in [(hrv,'night'),(daily,'rhr'),(sleep,'hours')]); quality='High' if coverage>=6 else 'Medium' if coverage>=4 else 'Low'

# Morning Report-style summary from fields the Personal API actually returned.
latest_daily_date=max((d for d in daily if d<=TODAY),default=None); current_daily=daily.get(latest_daily_date,{})
latest_sleep_date=max((d for d in sleep if d<=TODAY),default=None); current_sleep=sleep.get(latest_sleep_date,{})
latest_hrv_date=max((d for d in hrv if d<=TODAY),default=None); current_hrv=hrv.get(latest_hrv_date,{})
body_battery=current_daily.get('body_battery'); stress_now=current_daily.get('stress')
sleep_score=current_sleep.get('score'); hrv_status=current_hrv.get('status') or 'No status'
spo2_now=current_sleep.get('spo2') if current_sleep.get('spo2') is not None else current_daily.get('spo2')
spo2_low=current_sleep.get('spo2_min') if current_sleep.get('spo2_min') is not None else current_daily.get('spo2_min')
respiration_now=current_sleep.get('respiration') if current_sleep.get('respiration') is not None else current_daily.get('respiration')
morning_weighted=[]
for value,weight in [(rec,.40),(sleep_score,.25),(body_battery,.20),(clamp(100-stress_now) if stress_now is not None else None,.15)]:
    if value is not None:morning_weighted.append((value,weight))
morning_score=round(sum(v*w for v,w in morning_weighted)/sum(w for _,w in morning_weighted)) if morning_weighted else None
morning_label='Ready' if morning_score is not None and morning_score>=70 else 'Controlled' if morning_score is not None and morning_score>=50 else 'Recovery first' if morning_score is not None else 'Building baseline'

# Weekly training dose, intensity mix and latest-session details.
mon=TODAY-timedelta(days=TODAY.weekday())
week_dates={mon+timedelta(days=i) for i in range(7) if mon+timedelta(days=i)<=TODAY}
week_mod=sum(daily.get(d,{}).get('moderate') or 0 for d in week_dates)
week_vig=sum(daily.get(d,{}).get('vigorous') or 0 for d in week_dates)
week_intensity=week_mod+2*week_vig
intensity_goal=current_daily.get('intensity_goal') or 150
focus={'Low aerobic':0.0,'High aerobic':0.0,'Anaerobic':0.0,'Other':0.0}
focus_map={'Aerobic Base':'Low aerobic','Recovery':'Low aerobic','Tempo':'High aerobic','Lactate Threshold':'High aerobic','Vo2Max':'High aerobic','Anaerobic Capacity':'Anaerobic'}
for a in (x for x in acts if x['d']>=TODAY-timedelta(days=27)):
    focus[focus_map.get(a['te_label'],'Other')]+=a['load']
focus_total=sum(focus.values())
focus_pct={k:(v/focus_total*100 if focus_total else 0) for k,v in focus.items()}
latest_session=max(acts,key=lambda x:x['d'],default=None)

# Running economy and form. Efficiency is speed per heartbeat; higher is better.
run_eff=[(a,(60/a['pace'])/a['avg_hr']*100) for a in acts if a['run'] and a['pace'] and a['avg_hr']]
eff_recent=avg(v for a,v in run_eff if a['d']>=TODAY-timedelta(days=27))
eff_prior=avg(v for a,v in run_eff if TODAY-timedelta(days=111)<=a['d']<TODAY-timedelta(days=27))
eff_delta=((eff_recent/eff_prior)-1)*100 if eff_recent is not None and eff_prior else None
fitness_age_value=num(fitness_age.get('fitnessAge')) if isinstance(fitness_age,dict) else None
fitness_age_target=num(fitness_age.get('achievableFitnessAge')) if isinstance(fitness_age,dict) else None
chronological_age=num(fitness_age.get('chronologicalAge')) if isinstance(fitness_age,dict) else None

# Transparent goal markers.
runs=[a for a in acts if a['run']]; recent28=[a for a in acts if a['d']>=TODAY-timedelta(days=27)]; rr=[a for a in recent28 if a['run']]; strength=[a for a in recent28 if 'strength' in a['key']]
latest_run=max(runs,key=lambda x:x['d'],default=None)
lr90=max((a for a in runs if a['d']>=TODAY-timedelta(days=89)),key=lambda x:x['km'],default=None); lr=max(runs,key=lambda x:x['km'],default=None)
five=min((a for a in runs if 4.8<=a['km']<=5.3 and a['pace']),key=lambda x:x['pace'],default=None); target=240/42.195
pillars=[('Consistency',clamp(len(rr)/12*100),f'{len(rr)} runs / 28 days','Benchmark: 3 runs per week.'),('Endurance',clamp((lr90['km'] if lr90 else 0)/30*100),f"{(lr90['km'] if lr90 else 0):.1f} km longest / 90 days",'Benchmark: a visible 30 km long-run marker.'),('Speed reserve',clamp(target/five['pace']*100) if five else 0,(f"{int(five['pace'])}:{round(five['pace']%1*60):02d}/km best ~5K" if five else 'No comparable 5K'),'Compared with 5:41/km marathon target.'),('Strength',clamp(len(strength)/8*100),f'{len(strength)} sessions / 28 days','Benchmark: 2 sessions per week.'),('Recovery',rec or 0,f'{rec_label} · {rec if rec is not None else "—"}/100','HRV, RHR and sleep vs your baseline.')]

# Charts.
mon=TODAY-timedelta(days=TODAY.weekday()); starts=[mon-timedelta(weeks=i) for i in range(15,-1,-1)]; wm={d:{'distance':0,'load':0,'hours':0,'sessions':0} for d in starts}
for a in acts:
    w=a['d']-timedelta(days=a['d'].weekday())
    if w in wm:
        wm[w]['distance']+=a['km'];wm[w]['load']+=a['load'];wm[w]['hours']+=a['hrs'];wm[w]['sessions']+=1
weeks=[{'d':d.isoformat(),'label':d.strftime('%d %b'),**{k:round(v,2) for k,v in wm[d].items()}} for d in starts]
def series(src,key):return [{'d':d.isoformat(),'v':v[key]} for d,v in sorted(src.items()) if d>=TODAY-timedelta(days=364) and v.get(key) is not None]
sleep_series=[{'d':d.isoformat(),'v':round(v['hours'],2),'deep':round(v['deep'],2),'rem':round(v['rem'],2),'score':v['score']} for d,v in sorted(sleep.items()) if d>=TODAY-timedelta(days=364)]
sleep_score_series=series(sleep,'score')
body_battery_series=series(daily,'body_battery')
stress_series=series(daily,'stress')
spo2_series=[{'d':d.isoformat(),'v':v['spo2']} for d,v in sorted(sleep.items()) if d>=TODAY-timedelta(days=364) and v.get('spo2') is not None]
efficiency_series=[{'d':a['d'].isoformat(),'v':round(v,3)} for a,v in run_eff if a['d']>=TODAY-timedelta(days=364)]

# Monday-Sunday mini dashboard. Each of the recent weeks is precomputed so the
# browser slider changes the complete scorecard, not just its date label.
active_loads=[a['load'] for a in acts if a['load']>0]
median_active_load=statistics.median(active_loads) if active_loads else 75

def build_week_view(week_start):
    week_days=[week_start+timedelta(days=i) for i in range(7)]
    day_rows=[]
    for d in week_days:
        group=[a for a in acts if a['d']==d]
        km=sum(a['km'] for a in group); hours=sum(a['hrs'] for a in group); day_load=sum(a['load'] for a in group)
        dh=hrv.get(d,{}).get('night'); dr=daily.get(d,{}).get('rhr'); ds=sleep.get(d,{}).get('hours')
        recovery_parts=[]
        if dh is not None and hb:recovery_parts.append(clamp(50+((dh/hb)-1)*400))
        if dr is not None and rb is not None:recovery_parts.append(clamp(50-(dr-rb)*8))
        if ds is not None and sb is not None:recovery_parts.append(clamp(50+(ds-sb)*40))
        day_recovery=round(avg(recovery_parts)) if recovery_parts else None
        if d>TODAY:
            score=None; effect='Upcoming'; why='No score until the day is complete.'; recovery_hours=None
        elif group:
            stimulus=min(50,25+hours*12+(day_load/median_active_load)*12)
            goal_alignment=20 if any(a['run'] or 'strength' in a['key'] for a in group) else 12
            intensity=day_load/median_active_load if median_active_load else 0
            if day_recovery is None:match=15
            elif day_recovery<40 and intensity>1:match=5
            elif day_recovery<40 and intensity<=.75:match=25
            elif day_recovery>=60 and intensity>=.6:match=25
            else:match=18
            score=round(clamp(stimulus+goal_alignment+match))
            if any('strength' in a['key'] for a in group):effect='Strength stimulus'
            elif any(a['run'] and a['km']>=10 for a in group):effect='Endurance stimulus'
            elif day_load>median_active_load*1.35:effect='High aerobic load'
            elif any(a['run'] for a in group):effect='Aerobic maintenance'
            else:effect='General activity'
            why=f'{len(group)} session(s), {km:.1f} km and {day_load:.0f} training load.'
            recovery_hours=round(min(72,sum(6+a['load']*.12+a['hrs']*8 for a in group)))
        else:
            score=round((day_recovery or 50)*.7)
            effect='Recovery-only day' if day_recovery is not None else 'No activity recorded'
            why='Recovery was measured, but no training stimulus was recorded.' if day_recovery is not None else 'No activity or recovery data was recorded.'
            recovery_hours=0
        day_rows.append(dict(d=d,group=group,km=km,hours=hours,load=day_load,recovery=day_recovery,score=score,effect=effect,why=why,recovery_hours=recovery_hours,sleep=ds,hrv=dh,rhr=dr))

    elapsed=[x for x in day_rows if x['d']<=TODAY]
    week_km=sum(x['km'] for x in elapsed);week_load=sum(x['load'] for x in elapsed);week_sessions=sum(len(x['group']) for x in elapsed)
    elapsed_fraction=max(1/7,len(elapsed)/7);expected_sessions=max(1,4*elapsed_fraction)
    volume_score=clamp(week_km/typdist*100) if typdist else (100 if week_km else 0)
    consistency_score=clamp(week_sessions/expected_sessions*100)
    recovery_week=avg(x['recovery'] for x in elapsed)
    week_score=round(volume_score*.4+consistency_score*.3+(recovery_week or 50)*.3)
    week_effect='High stimulus' if typload and week_load>typload*1.3 else 'Building stimulus' if typload and week_load>=typload*.65 else 'Low stimulus so far'
    latest_training_day=max((x for x in elapsed if x['group']),key=lambda x:x['d'],default=None)
    remaining_recovery=0
    if week_start==mon and latest_training_day:
        remaining_recovery=max(0,(latest_training_day['recovery_hours'] or 0)-(TODAY-latest_training_day['d']).days*24)
    return dict(start=week_start,end=week_start+timedelta(days=6),days=day_rows,elapsed=elapsed,km=week_km,load=week_load,sessions=week_sessions,recovery=recovery_week,score=week_score,effect=week_effect,remaining_recovery=remaining_recovery,current=week_start==mon)

week_views=[build_week_view(start) for start in starts]
current_week=week_views[-1]; previous_week=week_views[-2]; week_before_previous=week_views[-3]
day_rows=current_week['days']; elapsed=current_week['elapsed']
week_km=current_week['km'];week_load=current_week['load'];week_sessions=current_week['sessions'];week_score=current_week['score'];week_effect=current_week['effect'];remaining_recovery=current_week['remaining_recovery']

# Current progress is compared with the same number of elapsed days last week.
stage_days=TODAY.weekday()+1
previous_stage=previous_week['days'][:stage_days]
previous_stage_km=sum(x['km'] for x in previous_stage);previous_stage_load=sum(x['load'] for x in previous_stage);previous_stage_sessions=sum(len(x['group']) for x in previous_stage)
last_week_km_delta=previous_week['km']-week_before_previous['km']
last_week_load_delta=previous_week['load']-week_before_previous['load']

suggestions=[]
if sd is not None and sd<-.3:suggestions.append(('Sleep extension',f'Your 7-day sleep is {abs(sd):.1f} h below baseline. Aim for 30–60 minutes more time in bed.'))
if hd is not None and hd<-5 and rd is not None and rd>2:suggestions.append(('Reduce strain','HRV is down while resting HR is up. Favor easy intensity, hydration, regular meals and an earlier night.'))
if week_sessions==0 and TODAY.weekday()>=2:suggestions.append(('Restart gently','No session is recorded this week. If you feel well, begin with 30–45 minutes easy rather than chasing missed volume.'))
if not strength:suggestions.append(('Add strength','No strength session is recorded in the last 28 days. Add two short sessions weekly when recovery is supportive.'))
if ratio is not None and ratio>1.4:suggestions.append(('Absorb the load','Seven-day load is well above normal. Keep the next session easy and protect sleep.'))
if not suggestions:suggestions.append(('Keep the rhythm','Recovery is close to baseline. Keep training consistent and avoid sudden jumps in load.'))
suggestions=suggestions[:3]

# Evidence-led insights requested by the user. These deliberately use matched
# observations and the user's own baselines. They describe association, not
# causation, and expose sample size / data limitations in the rendered cards.
daily_loads=defaultdict(float)
for a in acts:daily_loads[a['d']]+=a['load']

def week_stats(start):
    dates=[start+timedelta(days=i) for i in range(7)]
    week_acts=[a for a in acts if a['d'] in dates]
    return {
        'start':start,
        'run_km':sum(a['km'] for a in week_acts if a['run']),
        'load':sum(a['load'] for a in week_acts),
        'rhr':avg(daily.get(d,{}).get('rhr') for d in dates),
        'sessions':len(week_acts),
    }

complete_week_starts=[mon-timedelta(weeks=i) for i in range(12,0,-1)]
insight_weeks=[week_stats(start) for start in complete_week_starts]
last_complete=insight_weeks[-1]
prior_four=insight_weeks[-5:-1]
prior_run_km=avg(w['run_km'] for w in prior_four)
prior_rhr=avg(w['rhr'] for w in prior_four)
run_km_delta=last_complete['run_km']-prior_run_km if prior_run_km is not None else None
rhr_week_delta=last_complete['rhr']-prior_rhr if last_complete['rhr'] is not None and prior_rhr is not None else None
if prior_run_km and last_complete['run_km']>=prior_run_km*1.1 and rhr_week_delta is not None and rhr_week_delta>=2:
    fitness_fatigue_title='Load is rising faster than recovery'
    fitness_fatigue_summary='You ran more than your recent norm while resting heart rate also rose. That combination can accompany accumulated fatigue.'
    fitness_fatigue_action='Keep the next run easy and watch whether resting HR returns toward baseline over 2–3 mornings.'
    fitness_fatigue_tone='warning'
elif prior_run_km and last_complete['run_km']>=prior_run_km*.9 and rhr_week_delta is not None and rhr_week_delta<=0:
    fitness_fatigue_title='Fitness signals are supporting the work'
    fitness_fatigue_summary='Running volume held or increased while resting heart rate stayed stable or fell versus the prior four-week norm.'
    fitness_fatigue_action='Continue the gradual build; avoid turning a good week into a sudden load jump.'
    fitness_fatigue_tone='positive'
elif rhr_week_delta is not None and rhr_week_delta>=2:
    fitness_fatigue_title='Recovery looks more strained than fitness'
    fitness_fatigue_summary='Resting heart rate rose even without a clear increase in weekly running distance.'
    fitness_fatigue_action='Use sleep, HRV and how you feel to decide whether to reduce intensity temporarily.'
    fitness_fatigue_tone='warning'
else:
    fitness_fatigue_title='Fitness and fatigue signals are mixed'
    fitness_fatigue_summary='Weekly distance and resting heart rate do not yet point strongly in the same direction.'
    fitness_fatigue_action='Keep the next two weeks consistent; clearer patterns need repeated, comparable weeks.'
    fitness_fatigue_tone='neutral'

week_table_rows=''.join(
    f'<tr><th>{w["start"]:%d %b}</th><td>{w["run_km"]:.1f} km</td><td>{fmt(w["rhr"],0," bpm")}</td></tr>'
    for w in insight_weeks[-6:]
)
fitness_week_table=f'<table class="paired-table"><thead><tr><th>Week of</th><th>Running</th><th>Avg RHR</th></tr></thead><tbody>{week_table_rows}</tbody></table>'

def pace_at_hr(points,target):
    if len(points)<3:return None
    hrs=[x for x,_ in points];paces=[y for _,y in points];hm,pm=avg(hrs),avg(paces)
    denom=sum((x-hm)**2 for x in hrs)
    slope=sum((x-hm)*(y-pm) for x,y in points)/denom if denom else 0
    return pm+slope*(target-hm)

z2_floor=num(running_zone.get('zone2Floor'));z3_floor=num(running_zone.get('zone3Floor'))
runs90=[a for a in runs if a['d']>=TODAY-timedelta(days=89) and a['pace'] and a['avg_hr'] and 3<=a['pace']<=12 and a['hrs']>=.3]
easy_runs90=[a for a in runs90 if (z2_floor is None or a['avg_hr']>=z2_floor) and (z3_floor is None or a['avg_hr']<z3_floor)]
comparison_runs=easy_runs90 if len(easy_runs90)>=6 else runs90
same_hr_target=round(statistics.median(a['avg_hr'] for a in comparison_runs)) if comparison_runs else None
same_hr_recent_points=[(a['avg_hr'],a['pace']) for a in comparison_runs if a['d']>=TODAY-timedelta(days=44)]
same_hr_prior_points=[(a['avg_hr'],a['pace']) for a in comparison_runs if TODAY-timedelta(days=89)<=a['d']<TODAY-timedelta(days=44)]
same_hr_recent=pace_at_hr(same_hr_recent_points,same_hr_target) if same_hr_target is not None else None
same_hr_prior=pace_at_hr(same_hr_prior_points,same_hr_target) if same_hr_target is not None else None
same_hr_change_sec=(same_hr_recent-same_hr_prior)*60 if same_hr_recent is not None and same_hr_prior is not None else None
if same_hr_change_sec is not None and same_hr_change_sec<=-5:
    same_hr_title=f'Easy pace is {abs(same_hr_change_sec):.0f} sec/km faster at the same HR'
    same_hr_summary='Your adjusted pace improved while holding average heart rate constant across the two halves of the last 90 days.'
    same_hr_action='Treat this as encouraging economy evidence; confirm it on similar routes and conditions.'
    same_hr_tone='positive'
elif same_hr_change_sec is not None and same_hr_change_sec>=5:
    same_hr_title=f'Pace is {same_hr_change_sec:.0f} sec/km slower at the same HR'
    same_hr_summary='The recent 45-day adjusted pace is slower at the comparison heart rate, which can reflect fatigue, heat, hills or detraining.'
    same_hr_action='Compare route, temperature and recovery before changing training from this signal alone.'
    same_hr_tone='warning'
elif same_hr_change_sec is not None:
    same_hr_title='Pace at the same HR is broadly stable'
    same_hr_summary='The adjusted difference between the two 45-day periods is small.'
    same_hr_action='Keep collecting comparable easy runs; small changes are easily masked by terrain and weather.'
    same_hr_tone='neutral'
else:
    same_hr_title='More comparable easy runs are needed'
    same_hr_summary='Each 45-day window needs at least three runs with usable average heart rate and pace.'
    same_hr_action='Record easy runs consistently on similar terrain to unlock this comparison.'
    same_hr_tone='neutral'

body_battery_pairs=[]
for d,v in daily.items():
    if d<TODAY-timedelta(days=179) or v.get('body_battery_max') is None:continue
    body_battery_pairs.append((daily_loads.get(d-timedelta(days=1),0),v['body_battery_max']))
body_battery_r=pearson(body_battery_pairs);body_battery_effect=qeffect(body_battery_pairs)
if body_battery_effect is not None and body_battery_effect<=-5:
    battery_title=f'Harder days precede {abs(body_battery_effect):.0f} points less morning energy'
    battery_summary='After higher-load days, the next day’s Body Battery maximum was lower than after the lightest-load days.'
    battery_action='After high-load sessions, protect food, hydration and sleep and avoid stacking intensity automatically.'
    battery_tone='warning'
elif body_battery_effect is not None and body_battery_effect>=5:
    battery_title=f'Higher-load days preceded {body_battery_effect:.0f} points higher Body Battery max'
    battery_summary='This positive association likely reflects that harder training tends to happen during stronger recovery cycles; it does not show that training caused the higher value.'
    battery_action='Use the pattern to notice readiness cycles, not as a reason to train hard whenever Body Battery is high.'
    battery_tone='neutral'
elif body_battery_effect is not None:
    battery_title='Body Battery is fairly resilient to prior-day load'
    battery_summary='Next-day Body Battery maximum changes little between your highest- and lowest-load days.'
    battery_action='Use Body Battery with HRV, resting HR and perceived soreness rather than as a stand-alone green light.'
    battery_tone='positive' if body_battery_effect>=0 else 'neutral'
else:
    battery_title='Body Battery response needs more matched days'
    battery_summary='There are not yet enough next-day Body Battery observations for a stable comparison.'
    battery_action='Keep wearing the watch overnight and refresh the dashboard regularly.'
    battery_tone='neutral'

last_week_dates=[mon-timedelta(days=7)+timedelta(days=i) for i in range(7)]
last_week_sleep=avg(sleep.get(d,{}).get('hours') for d in last_week_dates)
last_week_need=avg((sleep.get(d,{}).get('need_min')/60) if sleep.get(d,{}).get('need_min') is not None else None for d in last_week_dates)
last_week_sleep_gap=last_week_sleep-last_week_need if last_week_sleep is not None and last_week_need is not None else None
last_week_load=sum(daily_loads.get(d,0) for d in last_week_dates)
last_week_runs=sum(a['km'] for a in acts if a['run'] and a['d'] in last_week_dates)

zone_seconds_28=[sum(a['zones'][i] for a in runs if a['d']>=TODAY-timedelta(days=27)) for i in range(5)]
zone_seconds_total=sum(zone_seconds_28);easy_zone_pct=(sum(zone_seconds_28[:2])/zone_seconds_total*100) if zone_seconds_total else None
hard_zone_pct=(sum(zone_seconds_28[2:])/zone_seconds_total*100) if zone_seconds_total else None

last_week_load_ratio=(insight_weeks[-1]['load']/insight_weeks[-2]['load']) if insight_weeks[-2]['load'] else None
load_jumps=[(insight_weeks[i]['load']/insight_weeks[i-1]['load'],insight_weeks[i]) for i in range(1,len(insight_weeks)) if insight_weeks[i-1]['load']>0]
biggest_jump=max(load_jumps,key=lambda x:x[0],default=(None,None))

next_hrv_pairs=[(load_value,hrv[d+timedelta(days=1)]['night']) for d,load_value in daily_loads.items() if load_value>0 and d+timedelta(days=1) in hrv and hrv[d+timedelta(days=1)].get('night') is not None and d>=TODAY-timedelta(days=179)]
next_hrv_r=pearson(next_hrv_pairs);next_hrv_effect=qeffect(next_hrv_pairs)
if next_hrv_effect is not None and next_hrv_effect>=2:
    hrv_load_title='Higher-load days were followed by higher HRV in this sample'
    hrv_load_summary='This likely reflects that harder sessions happened during stronger readiness cycles; it does not show that hard training raised HRV.'
    hrv_load_action='Judge the next hard session from the current HRV range, resting HR, sleep and how you feel.'
    hrv_load_tone='neutral'
elif next_hrv_effect is not None and next_hrv_effect<=-2:
    hrv_load_title='Higher-load days were followed by lower HRV'
    hrv_load_summary='The next night after harder active days averaged lower HRV than after lighter active days.'
    hrv_load_action='Avoid stacking demanding sessions when HRV also falls below your own balanced range.'
    hrv_load_tone='warning'
else:
    hrv_load_title='Training load has a weak next-night HRV relationship'
    hrv_load_summary='High- and low-load active days have produced similar next-night HRV so far.'
    hrv_load_action='Use a 3–4 day cluster with resting HR and sleep, not a single HRV reading.'
    hrv_load_tone='neutral'
stress_sleep_pairs=[(daily[d]['stress'],sleep[d+timedelta(days=1)]['score']) for d in daily if daily[d].get('stress') is not None and d+timedelta(days=1) in sleep and sleep[d+timedelta(days=1)].get('score') is not None and d>=TODAY-timedelta(days=179)]
stress_sleep_r=pearson(stress_sleep_pairs);stress_sleep_effect=qeffect(stress_sleep_pairs)

sleep28=[sleep[d] for d in sorted(sleep) if d>=TODAY-timedelta(days=27) and sleep[d].get('need_min') is not None]
sleep_need_met=sum(v['hours']*60>=v['need_min'] for v in sleep28)
sleep_need_gap=avg(v['hours']-v['need_min']/60 for v in sleep28)
bedtime_pairs=[]
for v in sleep.values():
    if v.get('start_ms') is None:continue
    start_dt=datetime.fromtimestamp(v['start_ms']/1000)
    bedtime_hour=start_dt.hour+start_dt.minute/60+(24 if start_dt.hour<12 else 0)
    bedtime_pairs.append((bedtime_hour,v['hours']))
bedtime_r=pearson(bedtime_pairs);bedtime_effect=qeffect(bedtime_pairs)
if len(bedtime_pairs)>=12:
    bed_x=[x for x,_ in bedtime_pairs];bed_y=[y for _,y in bedtime_pairs];bed_xm,bed_ym=avg(bed_x),avg(bed_y)
    bed_denom=sum((x-bed_xm)**2 for x in bed_x)
    bedtime_minutes_per_hour=(sum((x-bed_xm)*(y-bed_ym) for x,y in bedtime_pairs)/bed_denom*60) if bed_denom else None
else:bedtime_minutes_per_hour=None
if bedtime_minutes_per_hour is not None and bedtime_minutes_per_hour<=-5:
    bedtime_title=f'Each hour later bedtime aligns with {abs(bedtime_minutes_per_hour):.0f} minutes less sleep'
    bedtime_summary='Later sleep onset is associated with shorter total sleep in your recorded nights.'
    bedtime_action='Test a fixed wind-down alarm 30 minutes earlier for two weeks and compare the next report.'
    bedtime_tone='warning'
elif bedtime_minutes_per_hour is not None:
    bedtime_title='Bedtime timing has a weak link with sleep duration'
    bedtime_summary='Your recorded sleep onset explains little of the variation in total sleep so far.'
    bedtime_action='Keep wake time and wind-down routine consistent; reassess as more nights accumulate.'
    bedtime_tone='neutral'
else:
    bedtime_title='Not enough bedtime timestamps yet'
    bedtime_summary='The feed includes too few historical sleep-start timestamps to estimate this relationship responsibly.'
    bedtime_action='Keep sleep-window detection enabled; this card will calculate automatically when enough timestamps arrive.'
    bedtime_tone='neutral'

if last_week_sleep_gap is not None and last_week_sleep_gap<-.5:
    monday_change='Protect 30–45 minutes more time in bed on at least four nights this week.'
elif last_week_load_ratio is not None and last_week_load_ratio>1.3:
    monday_change='Hold training load near last week and make the next demanding session depend on recovery.'
elif easy_zone_pct is not None and easy_zone_pct<70:
    monday_change='Shift one run toward Zones 1–2 so hard work stays purposeful instead of becoming the default.'
elif not any('strength' in a['key'] and a['d'] in last_week_dates for a in acts):
    monday_change='Add one short strength session when recovery is supportive.'
else:
    monday_change='Keep the same rhythm and avoid a sudden jump in distance or load.'

last_week_load_detail=(f'{signed((last_week_load_ratio-1)*100,0,"% ")}vs prior week' if last_week_load_ratio is not None else ('previous week had 0 load' if insight_weeks[-2]['load']==0 else 'prior-week comparison unavailable'))
last_week_jump_summary=(f'Last complete week was {fmt((last_week_load_ratio-1)*100,0,"%")} versus the prior week.' if last_week_load_ratio is not None else f'Last complete week rose from {insight_weeks[-2]["load"]:.0f} to {insight_weeks[-1]["load"]:.0f} load, so a percentage change would be misleading.')

def coach_metric(label,value,detail=''):
    return f'<div><small>{html.escape(label)}</small><strong>{html.escape(value)}</strong><span>{html.escape(detail)}</span></div>'
def coach_card(kicker,title,summary,metrics,action,footer,tone='neutral',extra=''):
    metrics_html=''.join(coach_metric(*metric) for metric in metrics)
    return f'''<article class="coach-card {tone}"><header><span>{html.escape(kicker)}</span><b>{html.escape(title)}</b></header><p>{html.escape(summary)}</p><div class="coach-metrics">{metrics_html}</div>{extra}<div class="coach-action"><small>What to try</small><strong>{html.escape(action)}</strong></div><footer>{html.escape(footer)}</footer></article>'''

top_insights_html=''.join([
    coach_card('Fitness or fatigue',fitness_fatigue_title,fitness_fatigue_summary,[
        ('Last week running',fmt(last_complete['run_km'],1,' km'),f'{signed(run_km_delta,1," km")} vs prior 4-week average'),
        ('Last week resting HR',fmt(last_complete['rhr'],0,' bpm'),f'{signed(rhr_week_delta,1," bpm")} vs prior 4-week average'),
    ],fitness_fatigue_action,'Six complete Monday–Sunday weeks · distance and RHR shown together',fitness_fatigue_tone,fitness_week_table),
    coach_card('Same-heart-rate pace',same_hr_title,same_hr_summary,[
        ('Recent 45 days',pace_text(same_hr_recent),f'adjusted to {fmt(same_hr_target,0," bpm")}'),
        ('Previous 45 days',pace_text(same_hr_prior),f'{len(same_hr_prior_points)} comparable runs'),
        ('Change',f'{signed(same_hr_change_sec,0," sec/km")}',f'{len(same_hr_recent_points)} recent runs'),
    ],same_hr_action,'Regression-adjusted comparison · similar routes and weather improve confidence',same_hr_tone),
    coach_card('Body Battery after training',battery_title,battery_summary,[
        ('Association',f'r {body_battery_r:+.2f}' if body_battery_r is not None else '—',f'{len(body_battery_pairs)} matched days'),
        ('High vs low load',f'{signed(body_battery_effect,1," points")}', 'next-day maximum'),
    ],battery_action,'Daily maximum is used as a morning proxy because the feed has no timestamped wake value',battery_tone),
    coach_card(f'Monday report · {mon:%d %b}',f'Last week: {last_week_load:.0f} load and {last_week_runs:.1f} km running','A compact review of the last complete Monday–Sunday week.',[
        ('Training load',fmt(last_week_load,0),last_week_load_detail),
        ('Average sleep',fmt(last_week_sleep,1,' h'),f'{signed(last_week_sleep_gap,1," h")} vs sleep need'),
        ('Sleep need',fmt(last_week_need,1,' h'),'Garmin personalised estimate'),
    ],monday_change,'Regenerated on every refresh; the Monday card always uses the last complete week','priority'),
])

pattern_cards_html=''.join([
    coach_card('Sleep need','Sleep compared with what Garmin estimates your body needs',f'You met estimated sleep need on {sleep_need_met} of {len(sleep28)} measured nights in the last 28 days.',[
        ('Average gap',fmt(sleep_need_gap,1,' h'),'actual sleep minus need'),
    ],'Test a consistent lights-out window for two weeks, then reassess the gap.','Garmin sleep need is a personalised estimate, not a medical requirement','warning' if sleep_need_gap is not None and sleep_need_gap<-.5 else 'neutral'),
    coach_card('Intensity balance','How much running is easy versus hard', 'Heart-rate-zone time from runs in the last 28 days.',[
        ('Zones 1–2',fmt(easy_zone_pct,0,'%'),'easy aerobic time'),
        ('Zones 3–5',fmt(hard_zone_pct,0,'%'),'moderate-to-hard time'),
    ],'Keep most weekly running easy enough that quality sessions remain distinct.','Zone time only · sessions without HR-zone data are excluded','positive' if easy_zone_pct is not None and easy_zone_pct>=70 else 'warning'),
    coach_card('Weekly load jumps','Where training load changed suddenly',last_week_jump_summary,[
        ('Largest 12-week jump',fmt((biggest_jump[0]-1)*100 if biggest_jump[0] is not None else None,0,'%'),f'week of {biggest_jump[1]["start"]:%d %b}' if biggest_jump[1] else '—'),
    ],'Treat a large jump as a prompt to protect recovery, not as proof that the week was harmful.','Complete Monday–Sunday weeks; a jump is flagged by context, not a hard medical threshold','warning' if last_week_load_ratio is not None and last_week_load_ratio>1.3 else 'neutral'),
    coach_card('HRV after hard days',hrv_load_title,hrv_load_summary,[
        ('Association',f'r {next_hrv_r:+.2f}' if next_hrv_r is not None else '—',f'{len(next_hrv_pairs)} matched days'),
        ('High vs low load',fmt(next_hrv_effect,1,' ms'),'next-night HRV difference'),
        ('Current range',f'{fmt(current_hrv.get("balanced_low"),0)}–{fmt(current_hrv.get("balanced_high"),0)} ms',f'latest night {fmt(current_hrv.get("night"),0," ms")}'),
    ],hrv_load_action,'Garmin balanced range is your personal normal-range reference',hrv_load_tone),
    coach_card('Daytime stress → sleep','Whether stressful days align with that night’s sleep score','Pairs daytime average stress with the sleep score that follows.',[
        ('Association',f'r {stress_sleep_r:+.2f}' if stress_sleep_r is not None else '—',f'{len(stress_sleep_pairs)} matched days'),
        ('High vs low stress',fmt(stress_sleep_effect,0,' points'),'next sleep-score difference'),
    ],'On high-stress days, test a repeatable wind-down routine and compare the next four weeks.','Pattern in your data · association does not prove cause','warning' if stress_sleep_effect is not None and stress_sleep_effect<-5 else 'neutral'),
    coach_card('Bedtime → sleep duration',bedtime_title,bedtime_summary,[
        ('Per hour later',fmt(bedtime_minutes_per_hour,0,' min'),f'r {bedtime_r:+.2f}' if bedtime_r is not None else 'correlation unavailable'),
        ('Later vs earlier',fmt(bedtime_effect*60 if bedtime_effect is not None else None,0,' min'),f'{len(bedtime_pairs)} usable nights'),
    ],bedtime_action,'Sleep-start time and total sleep · association does not prove cause',bedtime_tone),
])

# Correlations + effect sizes + reasoning.
pairs1=[(sleep[d]['hours'],daily[d]['rhr']) for d in sleep.keys()&daily.keys() if daily[d]['rhr'] is not None]
pairs2=[(hrv[d]['night'],daily[d]['rhr']) for d in hrv.keys()&daily.keys() if hrv[d]['night'] is not None and daily[d]['rhr'] is not None]
loads=daily_loads
pairs3=[(v,hrv[d+timedelta(days=1)]['night']) for d,v in loads.items() if v and d+timedelta(days=1) in hrv and hrv[d+timedelta(days=1)]['night'] is not None]
pairs4=[(sleep[d]['hours'],daily[d]['body_battery_charge']) for d in sleep.keys()&daily.keys() if daily[d].get('body_battery_charge') is not None]
rels=[]
for kind,title,p in [('sleep','Sleep → resting HR',pairs1),('hrv','HRV ↔ resting HR',pairs2),('load','Training load → next-night HRV',pairs3),('battery','Sleep → Body Battery charge',pairs4)]:
    r=pearson(p);e=qeffect(p);strengthw='Strong' if r is not None and abs(r)>=.6 else 'Moderate' if r is not None and abs(r)>=.3 else 'Weak' if r is not None else 'Not enough data'
    if kind=='sleep' and e is not None: evidence=f"Your longest-sleep quartile averaged {abs(e):.1f} bpm {'lower' if e<0 else 'higher'} RHR than your shortest-sleep quartile."; meaning='Longer sleep aligns with a calmer cardiovascular signal.' if e<0 else 'Longer sleep has not aligned with lower RHR.'; use='Use sleep as context; confirm it with HRV and how you feel.'
    elif kind=='hrv' and e is not None: evidence=f"Your high-HRV quartile averaged {abs(e):.1f} bpm {'lower' if e<0 else 'higher'} RHR than your low-HRV quartile.";meaning='HRV and RHR reinforce the same recovery story.' if e<0 else 'HRV and RHR do not reinforce each other here.';use='Give more weight when HRV falls and RHR rises together.'
    elif kind=='load' and e is not None: evidence=f"After high-load days, next-night HRV averaged {abs(e):.1f} ms {'lower' if e<0 else 'higher'} than after low-load days.";meaning='Harder days show a recovery cost.' if e<0 and abs(e)>=2 else 'Load alone has not predicted HRV usefully.';use='Judge load with sleep and RHR, not by itself.'
    elif e is not None: evidence=f"Your longest-sleep quartile charged Body Battery {abs(e):.1f} points {'more' if e>0 else 'less'} than your shortest-sleep quartile.";meaning='Sleep duration is translating into overnight energy recharge.' if e>0 else 'More sleep has not produced a larger recharge in this sample.';use='Pair duration with sleep score and overnight stress before changing training.'
    else:evidence=meaning='Not enough matched observations.';use='Keep wearing the watch consistently.'
    rels.append((title,strengthw,r,len(p),evidence,meaning,use))

def week_for_browser(w):
    browser_days=[]
    for x in w['days']:
        status='future' if x['d']>TODAY else 'today' if x['d']==TODAY else 'past'
        recovery_text='—' if x['recovery_hours'] is None else ('None added' if x['recovery_hours']==0 else f"~{x['recovery_hours']} h")
        browser_days.append(dict(
            date=x['d'].isoformat(),weekday=x['d'].strftime('%a').upper(),dateLabel=x['d'].strftime('%d %b'),
            status=status,score=x['score'],effect=x['effect'],why=x['why'],km=round(x['km'],1),
            load=round(x['load']),sessions=len(x['group']),sleep=None if x['sleep'] is None else round(x['sleep'],1),recoveryText=recovery_text
        ))
    return dict(
        start=w['start'].isoformat(),end=w['end'].isoformat(),rangeLabel=f"{w['start']:%d %b}–{w['end']:%d %b}",
        current=w['current'],score=w['score'],effect=w['effect'],sessions=w['sessions'],km=round(w['km'],1),
        load=round(w['load']),recovery=None if w['recovery'] is None else round(w['recovery']),
        remainingRecovery=('Recovered' if w['remaining_recovery']==0 else f"~{w['remaining_recovery']} h") if w['current'] else 'Week complete',
        days=browser_days
    )

week_history=[week_for_browser(w) for w in week_views]
payload={'weeks':weeks,'weekHistory':week_history,'today':TODAY.isoformat(),'rhr':series(daily,'rhr'),'hrv':series(hrv,'night'),'sleep':sleep_series,'sleepScore':sleep_score_series,'bodyBattery':body_battery_series,'stress':stress_series,'spo2':spo2_series,'efficiency':efficiency_series,'weight':[{'d':x['d'].isoformat(),'v':x['kg']} for x in weights]}; js=json.dumps(payload,separators=(',',':')).replace('</','<\\/')
def signal(label,current,basev,delta,unit,good_up=True,pct=False):
    adjusted=(delta/100 if pct and delta is not None else delta);tone='neutral' if adjusted is None or abs(adjusted)<.04 else 'good' if (adjusted>0)==good_up else 'watch';return f'<article class="signal {tone}"><div><b>{label}</b><em>{signed(delta,1,"%" if pct else unit)}</em></div><strong>{fmt(current,1 if unit==" h" else 0,unit)}</strong><small>7-day average · baseline {fmt(basev,1 if unit==" h" else 0,unit)}</small></article>'
signals=signal('HRV',h7,hb,hd,' ms',True,True)+signal('Resting HR',r7,rb,rd,' bpm',False)+signal('Sleep',s7,sb,sd,' h')
pill_html=''.join(f'<article class="pillar"><div><b>{html.escape(n)}</b><strong>{s:.0f}</strong></div><i><u style="width:{s:.1f}%"></u></i><p>{html.escape(v)}</p><small>{html.escape(reason)}</small></article>' for n,s,v,reason in pillars)
rel_html=''.join(f'<article class="rel"><header><div><small>{html.escape(t)}</small><h3>{st} pattern</h3></div><b>r {"—" if r is None else f"{r:+.2f}"}</b></header><section><strong>What your data says</strong><p>{html.escape(ev)}</p></section><section><strong>Meaning</strong><p>{html.escape(me)}</p></section><section><strong>How to use it</strong><p>{html.escape(use)}</p></section><footer>{n} matched days · association, not causation</footer></article>' for t,st,r,n,ev,me,use in rels)
records=[]
for label,item,value in [('Longest run',lr,fmt(lr['km'] if lr else None,1,' km')),('Fastest ~5K',five,(f"{int(five['pace'])}:{round(five['pace']%1*60):02d}/km" if five else '—')),('Biggest load',max(acts,key=lambda x:x['load'],default=None),None),('Most climbing',max(acts,key=lambda x:x['elev'],default=None),None)]:
    if item:records.append((label,value or (fmt(item['load'],0) if label=='Biggest load' else fmt(item['elev'],0,' m')),f"{item['d']:%d %b %Y} · {item['name']}"))
records_html=''.join(f'<article class="record"><small>{html.escape(a)}</small><strong>{html.escape(b)}</strong><span>{html.escape(c)}</span></article>' for a,b,c in records)
wlatest=weights[-1]['kg'] if weights else None;wchange=weights[-1]['kg']-weights[0]['kg'] if len(weights)>1 else None;gaptext='—' if gap is None else 'Today' if gap==0 else f'{gap} days'
week_cards=''
for x in day_rows:
    status='future' if x['d']>TODAY else 'today' if x['d']==TODAY else 'past'
    score_text='—' if x['score'] is None else str(x['score'])
    recovery_text='—' if x['recovery_hours'] is None else ('None added' if x['recovery_hours']==0 else f"~{x['recovery_hours']} h")
    week_cards+=f'''<article class="day {status}"><header><div><small>{x['d']:%a}</small><strong>{x['d']:%d %b}</strong></div><span class="day-score">{score_text}</span></header><div class="effect">{html.escape(x['effect'])}</div><p>{html.escape(x['why'])}</p><div class="day-metrics"><span><b>{x['km']:.1f}</b> km</span><span><b>{x['load']:.0f}</b> load</span><span><b>{fmt(x['sleep'],1)}</b> sleep h</span></div><footer><span>Est. recovery</span><b>{recovery_text}</b></footer></article>'''
suggestions_html=''.join(f'<article><b>{html.escape(title)}</b><p>{html.escape(text)}</p></article>' for title,text in suggestions)
last_week_change=f"{signed(last_week_km_delta,1,' km')} distance · {signed(last_week_load_delta,0,' load')} vs the week before"
current_stage_change=f"vs the same point last week: {signed(week_km-previous_stage_km,1,' km')} · {signed(week_load-previous_stage_load,0,' load')}"
week_recap_html=f'''<article><small>Last week finished</small><strong>{previous_week['sessions']} sessions · {previous_week['km']:.1f} km · {previous_week['load']:.0f} load</strong><span>Score {previous_week['score']}/100 · {html.escape(last_week_change)}</span></article><article><small>This week so far</small><strong>{week_sessions} sessions · {week_km:.1f} km · {week_load:.0f} load</strong><span>{html.escape(current_stage_change)} · updates after every refresh</span></article>'''

def insight_card(label,value,context,tone=''):
    return f'<article class="insight {tone}"><small>{html.escape(label)}</small><strong>{html.escape(value)}</strong><span>{html.escape(context)}</span></article>'

morning_cards_html=''.join([
    insight_card('Dashboard readiness',f'{morning_score}/100' if morning_score is not None else '—',f'{morning_label} · blends trends, sleep, Body Battery and stress','primary'),
    insight_card('Body Battery',fmt(body_battery,0),f"Charged {fmt(current_daily.get('body_battery_charge'),0)} · range {fmt(current_daily.get('body_battery_min'),0)}–{fmt(current_daily.get('body_battery_max'),0)}"),
    insight_card('Sleep score',fmt(sleep_score,0),f"{current_sleep.get('score_label') or 'No rating'} · {fmt(current_sleep.get('hours'),1,' h')} slept"),
    insight_card('HRV status',hrv_status,f"Last night {fmt(current_hrv.get('night'),0,' ms')} · 7d {fmt(current_hrv.get('weekly'),0,' ms')}"),
    insight_card('Resting HR',fmt(current_daily.get('rhr'),0,' bpm'),f"7d {fmt(r7,0,' bpm')} · baseline {fmt(rb,0,' bpm')}"),
    insight_card('Daytime stress',fmt(stress_now,0),f"Maximum {fmt(current_daily.get('stress_max'),0)} · lower is generally calmer"),
    insight_card('Sleep SpO₂',fmt(spo2_now,0,'%'),f"Lowest reading {fmt(spo2_low,0,'%')} · trend only, not diagnosis"),
    insight_card('Respiration',fmt(respiration_now,0,' br/min'),'Sleep average · watch for sustained change'),
])

focus_colors={'Low aerobic':'#168f5b','High aerobic':'#2774df','Anaerobic':'#ed4337','Other':'#9aa3ae'}
focus_bar=''.join(f'<i style="width:{focus_pct[k]:.2f}%;background:{focus_colors[k]}" title="{k}: {focus_pct[k]:.0f}%"></i>' for k in focus)
focus_legend=''.join(f'<span><i style="background:{focus_colors[k]}"></i><b>{k}</b> {focus_pct[k]:.0f}%</span>' for k in focus if focus[k]>0)
zone_total=sum(latest_run['zones']) if latest_run else 0
zone_colors=['#9aa3ae','#168f5b','#f1b41c','#ff7a2f','#ed4337']
zone_bar=''.join(f'<i style="width:{(seconds/zone_total*100 if zone_total else 0):.2f}%;background:{zone_colors[i]}" title="Zone {i+1}: {(seconds/60):.0f} min"></i>' for i,seconds in enumerate(latest_run['zones'] if latest_run else [0]*5))
zone_legend=''.join(f'<span><i style="background:{zone_colors[i]}"></i>Z{i+1} {(seconds/60):.0f}m</span>' for i,seconds in enumerate(latest_run['zones'] if latest_run else [0]*5))
zone_floors=[num(running_zone.get(f'zone{i}Floor')) for i in range(1,6)] if running_zone else [None]*5
zone_ranges=[]
for i,floor in enumerate(zone_floors):
    if floor is None:continue
    ceiling=(zone_floors[i+1]-1) if i<4 and zone_floors[i+1] is not None else None
    zone_ranges.append(f'Z{i+1} {floor:.0f}{f"–{ceiling:.0f}" if ceiling is not None else "+"}')
zones_text=' · '.join(zone_ranges) if zone_ranges else 'No running-zone configuration returned'
latest_session_context=(f"{latest_session['d']:%d %b} · {latest_session['name']} · {latest_session['load']:.0f} load" if latest_session else 'No activity available')
latest_run_context=(f"{latest_run['d']:%d %b} · {latest_run['name']} · {latest_run['km']:.1f} km" if latest_run else 'No run available')

missing_metrics=[
    ('Training Readiness','No official readiness field in the downloaded Personal API records; the dashboard score is clearly labelled as its own calculation.'),
    ('Garmin Recovery Time','Not returned in the current payload. The weekly panel keeps its transparent local estimate.'),
    ('VO₂max + Race Predictor','Not present in the downloaded records, so the portal does not invent either value.'),
    ('Performance Condition','A live in-activity metric and absent from these summaries.'),
    ('Health Snapshot','No snapshot record was returned; use the watch or Garmin Connect when you want a shareable clinical trend record.'),
    ('Strength progression','Garmin records sessions and intensity, but weight × reps × sets still needs a lifting logbook.'),
]
missing_html=''.join(f'<article><b>{html.escape(name)}</b><p>{html.escape(reason)}</p></article>' for name,reason in missing_metrics)

doc=f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>My Sub-4 Dashboard</title><style>
:root{{--bg:#f5f7fa;--card:#fff;--ink:#17202a;--muted:#697386;--line:#e4e8ee;--red:#ed4337;--orange:#ff8b2c;--green:#168f5b;--blue:#2774df;--purple:#7157db;--shadow:0 10px 28px #1b26351a}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 Inter,Segoe UI,Arial,sans-serif}}.nav{{position:sticky;top:0;z-index:9;background:#ffffffed;border-bottom:1px solid var(--line);backdrop-filter:blur(10px)}}.nav div,.wrap{{width:min(1160px,calc(100% - 28px));margin:auto}}.nav div{{height:60px;display:flex;align-items:center;justify-content:space-between}}.nav b i{{color:var(--red);font-style:normal}}.nav a{{color:var(--muted);font-size:.78rem;font-weight:800;margin-left:16px;text-decoration:none}}.wrap{{padding:26px 0 60px}}.hero{{display:grid;grid-template-columns:1.3fr .7fr;gap:16px}}.verdict,.goal{{border-radius:22px;padding:30px;box-shadow:var(--shadow)}}.verdict{{background:#17202a;color:white}}.goal{{background:linear-gradient(145deg,var(--red),var(--orange));color:white}}.eyebrow{{font-size:.7rem;font-weight:900;text-transform:uppercase;letter-spacing:.13em;opacity:.7}}h1{{font-size:clamp(2.3rem,5vw,4.3rem);line-height:1;letter-spacing:-.055em;margin:8px 0 14px}}h2{{font-size:clamp(1.6rem,3vw,2.25rem);letter-spacing:-.04em;line-height:1.1;margin:0}}h3,p{{margin-top:0}}.verdict p{{color:#d5dbe2;font-size:1.05rem;max-width:680px}}.chip{{display:inline-block;background:#ffd43b;color:#17202a;border-radius:99px;padding:7px 11px;font-weight:900}}.goal .big{{font-size:3rem;font-weight:950;letter-spacing:-.06em;line-height:1;margin:12px 0}}.goal .big small{{display:block;font-size:.8rem;letter-spacing:.08em;margin-top:9px}}.goal-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:28px}}.goal-grid div{{background:#ffffff29;padding:11px;border-radius:11px}}.goal-grid small,.goal-grid strong{{display:block}}.section{{margin-top:38px;scroll-margin-top:75px}}.head{{display:flex;justify-content:space-between;align-items:end;gap:14px;margin-bottom:15px}}.head p{{color:var(--muted);margin:0;text-align:right}}.card,.signal,.pillar,.rel,.record{{background:var(--card);border:1px solid var(--line);box-shadow:var(--shadow)}}.reason{{padding:20px;border-radius:18px}}.reason-top{{display:flex;justify-content:space-between;margin-bottom:16px}}.quality{{color:var(--green);background:#e8f6ef;border-radius:99px;padding:5px 8px;font-size:.72rem;font-weight:900}}.flow{{display:grid;grid-template-columns:repeat(4,1fr);gap:24px}}.step{{position:relative;background:#f7f9fb;border:1px solid var(--line);border-radius:13px;padding:15px}}.step:not(:last-child):after{{content:'→';position:absolute;right:-19px;top:40%;color:#99a2af;font-size:1.4rem}}.step small{{color:var(--muted);font-weight:900;text-transform:uppercase}}.step strong{{display:block;margin:6px 0}}.step p{{font-size:.78rem;color:var(--muted);margin:0}}.signals{{display:grid;grid-template-columns:repeat(3,1fr);gap:11px;margin-top:12px}}.signal{{padding:17px;border-radius:14px}}.signal div{{display:flex;justify-content:space-between}}.signal em{{font-style:normal;font-size:.72rem;font-weight:900;background:#eef1f4;padding:4px 7px;border-radius:99px}}.signal.good em{{color:var(--green);background:#e8f6ef}}.signal.watch em{{color:#b14d21;background:#fff0e7}}.signal>strong{{display:block;font-size:1.9rem;margin:7px 0}}.signal small{{color:var(--muted)}}details{{background:white;border:1px solid var(--line);border-radius:12px;margin-top:11px}}summary{{cursor:pointer;padding:12px 15px;font-weight:850}}details p{{padding:0 15px 14px;color:var(--muted)}}.pillars{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}}.pillar{{padding:15px;border-radius:14px}}.pillar>div{{display:flex;justify-content:space-between}}.pillar>div strong{{color:var(--blue)}}.pillar i{{display:block;height:7px;background:#e9edf2;border-radius:9px;margin:11px 0;overflow:hidden}}.pillar u{{display:block;height:100%;background:linear-gradient(90deg,var(--red),var(--orange));text-decoration:none}}.pillar p{{font-size:.82rem;font-weight:800;margin:0 0 5px}}.pillar small{{color:var(--muted)}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:12px}}.metric{{padding:15px;border-radius:13px;background:white;border:1px solid var(--line)}}.metric small{{color:var(--muted);text-transform:uppercase;font-weight:900}}.metric strong{{display:block;font-size:1.55rem;margin:3px 0}}.charts{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.chart-card{{padding:17px;border-radius:16px;min-width:0}}.chart-head{{display:flex;justify-content:space-between}}.chart-head h3{{margin:0}}.chart-head p{{font-size:.76rem;color:var(--muted)}}.range{{background:#eef1f4;padding:3px;border-radius:8px;white-space:nowrap}}.range button{{border:0;background:transparent;padding:5px 7px;border-radius:6px;color:var(--muted);font-weight:800;cursor:pointer}}.range button.active{{background:white;color:var(--ink)}}svg{{width:100%;height:auto}}svg text{{font:10px Segoe UI;fill:#7a8491}}.gridline{{stroke:#e6e9ed}}.relationships{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.rel{{border-radius:16px;overflow:hidden}}.rel header{{display:flex;justify-content:space-between;padding:17px;border-bottom:1px solid var(--line)}}.rel header small{{color:var(--muted);text-transform:uppercase;font-weight:900}}.rel header h3{{margin:3px 0 0}}.rel header>b{{color:var(--blue);background:#edf3ff;padding:7px;border-radius:8px;height:max-content}}.rel section{{padding:13px 17px}}.rel section:nth-of-type(1){{background:#f7f9fc}}.rel section strong{{font-size:.72rem;text-transform:uppercase}}.rel section p{{color:var(--muted);font-size:.82rem;margin:4px 0 0}}.rel footer{{padding:10px 17px;color:var(--muted);font-size:.7rem;border-top:1px solid var(--line)}}.records{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.record{{padding:15px;border-radius:14px}}.record small{{text-transform:uppercase;color:var(--muted);font-weight:900}}.record strong,.record span{{display:block}}.record strong{{font-size:1.35rem;margin:9px 0}}.record span{{color:var(--muted);font-size:.78rem}}.footer{{margin-top:38px;padding-top:15px;border-top:1px solid var(--line);color:var(--muted);font-size:.75rem}}#tip{{display:none;position:fixed;z-index:20;background:#17202a;color:white;padding:8px 10px;border-radius:8px;font-size:.75rem;pointer-events:none}}
@media(max-width:880px){{.hero{{grid-template-columns:1fr}}.flow{{grid-template-columns:1fr 1fr}}.step:after{{display:none}}.pillars{{grid-template-columns:1fr 1fr}}.relationships{{grid-template-columns:1fr}}}}@media(max-width:620px){{.nav nav{{display:none}}.verdict,.goal{{padding:22px}}.flow,.signals,.charts{{grid-template-columns:1fr}}.metrics{{grid-template-columns:1fr 1fr}}.pillars,.records{{grid-template-columns:1fr}}.head{{display:block}}.head p{{text-align:left;margin-top:5px}}}}
</style><style>
.nav>div{{width:min(1160px,calc(100% - 28px));margin:auto;height:60px;display:flex;align-items:center;justify-content:space-between}}.nav-actions{{display:flex;align-items:center;gap:11px;width:auto!important;margin:0!important}}.refresh-btn{{border:0;background:var(--ink);color:white;border-radius:10px;padding:9px 13px;font-weight:900;cursor:pointer;white-space:nowrap}}.refresh-btn:hover{{background:var(--blue)}}.refresh-btn:disabled{{opacity:.6;cursor:wait}}.refresh-state{{font-size:.72rem;color:var(--muted)}}.week-summary{{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:18px;padding:18px 20px;border-radius:18px;margin-bottom:12px}}.week-ring{{--score:0;width:78px;height:78px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(var(--red) calc(var(--score)*1%),#e9edf2 0);position:relative}}.week-ring:before{{content:'';position:absolute;inset:8px;border-radius:50%;background:white}}.week-ring b{{position:relative;font-size:1.35rem}}.week-overview h3{{margin:0 0 4px}}.week-overview p{{margin:0;color:var(--muted)}}.recovery-now{{text-align:right}}.recovery-now small,.recovery-now strong{{display:block}}.recovery-now small{{color:var(--muted);text-transform:uppercase;font-weight:900}}.recovery-now strong{{font-size:1.35rem}}.week-days{{display:grid;grid-template-columns:repeat(7,minmax(150px,1fr));gap:9px;overflow-x:auto;padding:2px 2px 8px}}.day{{background:white;border:1px solid var(--line);border-radius:15px;padding:13px;min-height:255px;box-shadow:var(--shadow)}}.day.today{{border:2px solid var(--red)}}.day.future{{opacity:.62}}.day header{{display:flex;justify-content:space-between;align-items:start}}.day header small,.day header strong{{display:block}}.day header small{{text-transform:uppercase;color:var(--muted);font-weight:900}}.day-score{{width:42px;height:42px;border-radius:50%;display:grid;place-items:center;background:#edf3ff;color:var(--blue);font-weight:950}}.effect{{font-weight:900;margin:15px 0 6px}}.day>p{{font-size:.76rem;color:var(--muted);min-height:54px}}.day-metrics{{display:grid;gap:4px;border-top:1px solid var(--line);padding-top:9px;font-size:.76rem}}.day-metrics span{{display:flex;justify-content:space-between}}.day footer{{display:flex;justify-content:space-between;gap:8px;margin-top:10px;padding-top:9px;border-top:1px solid var(--line);font-size:.72rem}}.suggestions{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}}.suggestions article{{background:#eef6ff;border:1px solid #d9e8fb;border-radius:13px;padding:14px}}.suggestions p{{font-size:.8rem;color:var(--muted);margin:5px 0 0}}@media(max-width:880px){{.suggestions{{grid-template-columns:1fr}}}}@media(max-width:620px){{.nav nav,.refresh-state{{display:none}}.refresh-btn{{padding:8px 10px}}.week-summary{{grid-template-columns:auto 1fr}}.recovery-now{{grid-column:1/-1;text-align:left}}}}
</style></head><body><div class="nav"><div><b>MY <i>SUB-4</i> DASHBOARD</b><div class="nav-actions"><nav><a href="#today">Today</a><a href="#morning">Morning</a><a href="#insights">Insights</a><a href="#week">Week</a><a href="#training">Training</a><a href="#running">Running</a><a href="#health">Health</a></nav><span id="refreshState" class="refresh-state">Last: {last_refresh_display}<small>Auto every 2 hours</small></span><button id="refreshButton" class="refresh-btn" type="button">↻ Refresh data</button></div></div></div><main class="wrap"><div id="refreshToast" class="refresh-toast" role="status"></div>
<section class="hero" id="today"><article class="verdict"><div class="eyebrow">Today’s read · {TODAY:%d %B %Y}</div><h1>{html.escape(verdict)}</h1><p>{html.escape(action)}</p><span class="chip">Primary focus: consistency</span></article><aside class="goal"><div class="eyebrow">Your goal</div><div class="big">SUB 4:00<small>Marathon · 5:41 per km</small></div><div class="goal-grid"><div><small>Latest run</small><strong>{gaptext}</strong></div><div><small>Longest run</small><strong>{fmt(lr['km'] if lr else None,1,' km')}</strong></div></div></aside></section>
<section class="section"><div class="head"><div><div class="eyebrow">Reasoning trail</div><h2>Why it says that</h2></div><p>Every conclusion is traceable to your baseline.</p></div><div class="card reason"><div class="reason-top"><b>Signal chain</b><span class="quality">{quality} data coverage</span></div><div class="flow"><div class="step"><small>1 · Training</small><strong>{load7:.0f} load · {dist:.1f} km</strong><p>Last 7 days vs typical {typload:.0f} load and {typdist:.1f} km.</p></div><div class="step"><small>2 · Sleep</small><strong>{fmt(s7,1,' h')}</strong><p>{signed(sd,1,' h')} vs your prior baseline.</p></div><div class="step"><small>3 · Body response</small><strong>HRV {signed(hd,1,'%')} · RHR {signed(rd,1)}</strong><p>Two recovery markers read together.</p></div><div class="step"><small>4 · Decision</small><strong>{html.escape(verdict)}</strong><p>{html.escape(action)}</p></div></div></div><div class="signals">{signals}</div><details><summary>How recovery is calculated</summary><p>Recovery is separate from training load. It combines HRV, resting heart rate and sleep versus your previous 28-day baseline. A missing workout never lowers recovery. Current recovery: <b>{rec if rec is not None else '—'}/100 ({rec_label})</b>. Directional training aid, not medical advice.</p></details></section>
<section class="section" id="morning"><div class="head"><div><div class="eyebrow">Morning report · {latest_sleep_date:%d %b %Y}</div><h2>Can I absorb training today?</h2></div><p>Official Garmin measurements, combined with a transparent dashboard score.</p></div><div class="insight-grid">{morning_cards_html}</div><details><summary>How to use this morning check</summary><p><b>{morning_label}:</b> the dashboard score is not Garmin Training Readiness. It weights your recovery trend 40%, sleep score 25%, Body Battery 20% and inverse stress 15%, using only available fields. Look for a 3–4 day cluster, not one noisy reading. A low Pulse Ox value can be affected by fit, movement or altitude; sustained or concerning readings belong with a clinician.</p></details></section>
<section class="section" id="insights"><div class="head"><div><div class="eyebrow">Insights from your own data</div><h2>What is worth acting on?</h2></div><p>Evidence, confidence and one practical experiment—not just charts.</p></div><div class="insight-notice"><b>Observations, not medical advice.</b><span>Patterns show what tends to move together in your Garmin data; they do not prove what caused the change.</span></div><div class="coach-grid">{top_insights_html}</div><div class="subhead"><div><div class="eyebrow">Patterns worth testing</div><h3>Go beyond the headline metrics</h3></div><p>Each card states its time window and data limitation.</p></div><div class="pattern-grid">{pattern_cards_html}</div></section>
<section class="section" id="week"><div class="head"><div><div class="eyebrow" id="weekRangeLabel">Monday–Sunday · {mon:%d %b}–{(mon+timedelta(days=6)):%d %b}</div><h2 id="weekHeading">This week at a glance</h2></div><p>Slide through recent weeks; every scorecard uses the same transparent method.</p></div><div class="week-navigator" aria-label="Choose a training week"><button id="weekPrev" type="button" aria-label="Previous week">←</button><div class="week-slider"><div><b id="weekSliderLabel">Current week</b><span id="weekSliderCount">Week {len(week_history)} of {len(week_history)}</span></div><input id="weekSlider" type="range" min="0" max="{len(week_history)-1}" value="{len(week_history)-1}" step="1" aria-label="Training week"></div><button id="weekNext" type="button" aria-label="Next week" disabled>→</button><button id="weekCurrent" class="current-week-btn" type="button">Current week</button></div><div class="week-recap" id="weekRecap" aria-live="polite">{week_recap_html}</div><div class="card week-summary" id="weekSummary"><div class="week-ring" id="weekRing" style="--score:{week_score}"><b id="weekScore">{week_score}</b></div><div class="week-overview"><h3 id="weekEffect">{html.escape(week_effect)}</h3><p id="weekTotals">{week_sessions} sessions · {week_km:.1f} km · {week_load:.0f} load. Score = 40% volume, 30% consistency and 30% recovery.</p></div><div class="recovery-now"><small id="weekRecoveryLabel">Estimated remaining recovery</small><strong id="weekRecovery">{'Recovered' if remaining_recovery==0 else f'~{remaining_recovery} h'}</strong></div></div><div class="week-days" id="weekDays">{week_cards}</div><div id="weekCurrentAdvice"><div class="suggestions">{suggestions_html}</div><details><summary>How daily scores and recovery time are estimated</summary><p>A day score uses up to 50 points for useful training stimulus, 20 for alignment with running/strength goals, and 30 for matching effort to that day’s HRV, resting HR and sleep. No-activity days are marked as recovery-only rather than automatically good or bad. Recovery time is a local estimate from duration and training load; it is not Garmin’s official recovery-time field.</p></details></div></section>
<section class="section" id="training"><div class="head"><div><div class="eyebrow">Training dose + intent</div><h2>What system did the work train?</h2></div><p>Acute load, intensity minutes, load focus and per-session Training Effect.</p></div><div class="training-grid"><article class="card training-card"><small>Acute training load</small><strong>{load7:.0f}</strong><p>{fmt(ratio,1,'×')} your previous four-week weekly average. {html.escape('A large jump raises fatigue and injury risk.' if ratio and ratio>1.4 else 'Load is within your recent pattern.')}</p></article><article class="card training-card"><small>Intensity minutes</small><strong>{week_intensity:.0f} / {intensity_goal:.0f}</strong><p>{week_mod:.0f} moderate + {week_vig:.0f} vigorous minutes; vigorous counts double toward Garmin’s goal.</p></article><article class="card training-card wide"><small>28-day load focus</small><div class="stack">{focus_bar}</div><div class="stack-legend">{focus_legend}</div><p>For marathon development, most load should accumulate aerobically while harder work stays purposeful.</p></article><article class="card training-card"><small>Latest session effect</small><strong>{fmt(latest_session['aerobic_te'] if latest_session else None,1)} aerobic · {fmt(latest_session['anaerobic_te'] if latest_session else None,1)} anaerobic</strong><p>{html.escape(latest_session['te_label'] if latest_session and latest_session['te_label'] else 'No label')} · {html.escape(latest_session_context)}</p></article><article class="card training-card wide"><small>Latest run heart-rate distribution</small><div class="stack">{zone_bar}</div><div class="stack-legend compact">{zone_legend}</div><p>{html.escape(latest_run_context)} · avg HR {fmt(latest_run['avg_hr'] if latest_run else None,0,' bpm')}. Use this to confirm an easy run stayed easy or a quality session reached its intended zones.</p></article><article class="card training-card"><small>Strength context</small><strong>{len(strength)} sessions / 28d</strong><p>Garmin captures session fatigue and intensity minutes, but not progressive overload quality. Keep weight × reps × sets in a logbook.</p></article></div></section>
<section class="section" id="goal"><div class="head"><div><div class="eyebrow">Sub-4 marathon</div><h2>Five things that move the goal</h2></div><p>Every bar names its benchmark.</p></div><div class="pillars">{pill_html}</div></section>
<section class="section" id="running"><div class="head"><div><div class="eyebrow">Running performance</div><h2>Is the engine becoming more economical?</h2></div><p>Pace-to-heart-rate, running dynamics and your configured threshold zones.</p></div><div class="insight-grid run-grid"><article class="insight primary"><small>Latest run</small><strong>{pace_text(latest_run['pace'] if latest_run else None)} @ {fmt(latest_run['avg_hr'] if latest_run else None,0,' bpm')}</strong><span>{html.escape(latest_run_context)}</span></article><article class="insight"><small>HR efficiency index</small><strong>{fmt(eff_recent,2)}</strong><span>{signed(eff_delta,1,'%')} vs the prior 12 weeks · higher means more speed per heartbeat</span></article><article class="insight"><small>Cadence + ground contact</small><strong>{fmt(latest_run['cadence'] if latest_run else None,0,' spm')} · {fmt(latest_run['ground_contact'] if latest_run else None,0,' ms')}</strong><span>Compare like-for-like runs; treadmill and outdoor mechanics differ</span></article><article class="insight"><small>Vertical form + stride</small><strong>{fmt(latest_run['vertical_osc'] if latest_run else None,1,' cm')} · {fmt(latest_run['stride_cm'] if latest_run else None,0,' cm')}</strong><span>Vertical ratio {fmt(latest_run['vertical_ratio'] if latest_run else None,1,'%')} · trends matter more than a universal target</span></article><article class="insight wide"><small>Running HR zones</small><strong>{html.escape(zones_text)}</strong><span>{html.escape(str(running_zone.get('trainingMethod') or 'Unknown').replace('_',' ').title())} method · LTHR {fmt(num(running_zone.get('lactateThresholdHeartRateUsed')),0,' bpm')} · max HR {fmt(num(running_zone.get('maxHeartRateUsed')),0,' bpm')}</span></article></div><article class="card chart-card solo"><div class="chart-head"><div><h3>Running heart-rate efficiency</h3><p>Speed per heartbeat · use the trend, and compare similar surfaces</p></div><div class="range" data-id="efficiencyChart"><button data-days="30">30d</button><button class="active" data-days="90">90d</button><button data-days="365">1y</button></div></div><svg id="efficiencyChart" viewBox="0 0 800 240"></svg></article></section>
<section class="section" id="health"><div class="head"><div><div class="eyebrow">Health baseline</div><h2>What is changing outside workouts?</h2></div><p>Fitness Age, daily movement and overnight physiology.</p></div><div class="insight-grid health-grid"><article class="insight primary"><small>Fitness Age</small><strong>{fmt(fitness_age_value,1)} years</strong><span>Chronological {fmt(chronological_age,0)} · achievable {fmt(fitness_age_target,1)}</span></article><article class="insight"><small>Weight</small><strong>{fmt(wlatest,1,' kg')}</strong><span>{signed(wchange,1,' kg')} across {len(weights)} weigh-ins · more entries improve the trend</span></article><article class="insight"><small>Steps today</small><strong>{fmt(current_daily.get('steps'),0)}</strong><span>Goal {fmt(current_daily.get('step_goal'),0)} · today may still be in progress</span></article><article class="insight"><small>Active calories today</small><strong>{fmt(current_daily.get('active_calories'),0,' kcal')}</strong><span>Total {fmt(current_daily.get('total_calories'),0,' kcal')} so far</span></article></div><div class="charts health-charts"><article class="card chart-card"><div class="chart-head"><div><h3>Body Battery</h3><p>Daily latest value</p></div></div><svg id="bodyBatteryChart" viewBox="0 0 800 240"></svg></article><article class="card chart-card"><div class="chart-head"><div><h3>Daily stress</h3><p>Lower resting stress is generally better</p></div></div><svg id="stressChart" viewBox="0 0 800 240"></svg></article><article class="card chart-card"><div class="chart-head"><div><h3>Sleep score</h3><p>Quality plus duration</p></div></div><svg id="sleepScoreChart" viewBox="0 0 800 240"></svg></article><article class="card chart-card"><div class="chart-head"><div><h3>Sleep SpO₂</h3><p>Trend only · not a medical diagnosis</p></div></div><svg id="spo2Chart" viewBox="0 0 800 240"></svg></article></div><details><summary>Health interpretation boundaries</summary><p>Fitness Age, stress, Body Battery, sleep, respiration and Pulse Ox are useful personal trends. They do not measure kidney function, lipids or uric acid, and they do not replace medical review or blood tests.</p></details></section>
<section class="section" id="trends"><div class="head"><div><div class="eyebrow">Training + recovery</div><h2>Trends with context</h2></div><p>Hover or tap for exact values.</p></div><div class="metrics"><div class="metric"><small>Last 7 days</small><strong>{dist:.1f} km</strong><span>{len(recent)} sessions</span></div><div class="metric"><small>Typical week</small><strong>{typdist:.1f} km</strong><span>previous 4-week avg</span></div><div class="metric"><small>Recovery</small><strong>{rec if rec is not None else '—'}/100</strong><span>{rec_label}</span></div><div class="metric"><small>Latest activity</small><strong>{gaptext}</strong><span>{latest.strftime('%d %b %Y') if latest else '—'}</span></div></div><div class="charts">
<article class="card chart-card"><div class="chart-head"><div><h3>Weekly distance</h3><p>Am I training consistently?</p></div></div><svg id="distanceChart" viewBox="0 0 800 240"></svg></article><article class="card chart-card"><div class="chart-head"><div><h3>Weekly load</h3><p>Is stimulus rising faster than recovery?</p></div></div><svg id="loadChart" viewBox="0 0 800 240"></svg></article>
<article class="card chart-card"><div class="chart-head"><div><h3>Resting HR</h3><p>7d {fmt(r7,0,' bpm')} · baseline {fmt(rb,0,' bpm')}</p></div><div class="range" data-id="rhrChart"><button data-days="30">30d</button><button class="active" data-days="90">90d</button><button data-days="365">1y</button></div></div><svg id="rhrChart" viewBox="0 0 800 240"></svg></article><article class="card chart-card"><div class="chart-head"><div><h3>Nightly HRV</h3><p>7d {fmt(h7,0,' ms')} · baseline {fmt(hb,0,' ms')}</p></div><div class="range" data-id="hrvChart"><button data-days="30">30d</button><button class="active" data-days="90">90d</button><button data-days="365">1y</button></div></div><svg id="hrvChart" viewBox="0 0 800 240"></svg></article>
<article class="card chart-card"><div class="chart-head"><div><h3>Sleep</h3><p>7d {fmt(s7,1,' h')} · baseline {fmt(sb,1,' h')}</p></div><div class="range" data-id="sleepChart"><button data-days="30">30d</button><button class="active" data-days="90">90d</button><button data-days="365">1y</button></div></div><svg id="sleepChart" viewBox="0 0 800 240"></svg></article><article class="card chart-card"><div class="chart-head"><div><h3>Weight</h3><p>Latest {fmt(wlatest,1,' kg')} · change {signed(wchange,1,' kg')} · only {len(weights)} weigh-ins</p></div></div><svg id="weightChart" viewBox="0 0 800 240"></svg></article></div></section>
<section class="section" id="relationships"><div class="head"><div><div class="eyebrow">Personal relationships</div><h2>What actually moves together</h2></div><p>Effect size + interpretation + action.</p></div><div class="relationships">{rel_html}</div><details><summary>How to read correlation</summary><p><b>r</b> runs from −1 to +1. The sign is direction; distance from zero is strength. Quartile comparisons show the real-world size. Association does not prove cause.</p></details></section>
<section class="section" id="coverage"><div class="head"><div><div class="eyebrow">Data coverage</div><h2>Important guide metrics not in this feed</h2></div><p>Visible gaps prevent false confidence.</p></div><div class="missing-grid">{missing_html}</div></section>
<section class="section"><div class="head"><div><div class="eyebrow">Reference points</div><h2>Your standout days</h2></div></div><div class="records">{records_html}</div></section><footer class="footer">{len(acts)} activities · updated {TODAY:%d %b %Y} · private dashboard · not medical advice</footer></main><div id="tip"></div>
<script>const DATA={js},NS='http://www.w3.org/2000/svg',tip=document.getElementById('tip');const mk=(t,a={{}})=>{{let e=document.createElementNS(NS,t);Object.entries(a).forEach(([k,v])=>e.setAttribute(k,v));return e}};function show(e,s){{tip.innerHTML=s;tip.style.display='block';tip.style.left=Math.min(e.clientX+12,innerWidth-245)+'px';tip.style.top=Math.max(8,e.clientY-25)+'px'}}function axes(svg,min,max){{let b={{l:44,r:786,t:14,bt:198}};for(let i=0;i<4;i++){{let y=b.t+(b.bt-b.t)*i/3;svg.append(mk('line',{{x1:b.l,y1:y,x2:b.r,y2:y,class:'gridline'}}));let tx=mk('text',{{x:38,y:y+4,'text-anchor':'end'}});tx.textContent=(max-(max-min)*i/3).toFixed(0);svg.append(tx)}}return b}}function line(id,src,color,unit,days=90,extra=null){{let svg=document.getElementById(id);svg.innerHTML='';if(!src.length){{svg.innerHTML='<text x="400" y="110" text-anchor="middle">Not enough data</text>';return}}let end=new Date(src.at(-1).d),start=new Date(end);start.setDate(end.getDate()-days+1);let p=src.filter(x=>new Date(x.d)>=start),vs=p.map(x=>x.v),lo=Math.min(...vs),hi=Math.max(...vs),pad=Math.max((hi-lo)*.15,unit===' kg'?.4:unit===' index'?.03:1);lo-=pad;hi+=pad;if(['bodyBatteryChart','stressChart','sleepScoreChart','spo2Chart'].includes(id)){{lo=Math.max(0,lo);hi=Math.min(100,hi)}}let b=axes(svg,lo,hi),x=i=>b.l+(b.r-b.l)*(p.length==1?.5:i/(p.length-1)),y=v=>b.bt-(v-lo)/(hi-lo)*(b.bt-b.t);svg.append(mk('path',{{d:p.map((q,i)=>(i?'L':'M')+x(i)+','+y(q.v)).join(' '),fill:'none',stroke:color,'stroke-width':3}}));p.forEach((q,i)=>{{let c=mk('circle',{{cx:x(i),cy:y(q.v),r:7,fill:'transparent',tabindex:0}}),s=`<b>${{q.d}}</b><br>${{q.v.toFixed(unit===' kg'?1:unit===' h'||unit===' index'?2:0)}}${{unit}}${{extra?extra(q):''}}`;c.onpointerenter=e=>show(e,s);c.onpointermove=e=>show(e,s);c.onpointerleave=()=>tip.style.display='none';svg.append(c)}})}}function bars(id,key,color,unit){{let svg=document.getElementById(id),p=DATA.weeks,m=Math.max(...p.map(x=>x[key]),1),b=axes(svg,0,m),slot=(b.r-b.l)/p.length,w=slot*.62;p.forEach((q,i)=>{{let h=q[key]/m*(b.bt-b.t),r=mk('rect',{{x:b.l+i*slot+(slot-w)/2,y:b.bt-h,width:w,height:Math.max(h,2),rx:4,fill:color}}),s=`<b>Week of ${{q.d}}</b><br>${{q[key].toFixed(1)}}${{unit}} · ${{q.sessions}} sessions · ${{q.hours.toFixed(1)}} h`;r.onpointerenter=e=>show(e,s);r.onpointermove=e=>show(e,s);r.onpointerleave=()=>tip.style.display='none';svg.append(r)}})}}let cfg={{rhrChart:[DATA.rhr,'#ed4337',' bpm',null],hrvChart:[DATA.hrv,'#2774df',' ms',null],sleepChart:[DATA.sleep,'#7157db',' h',q=>`<br>Deep ${{q.deep.toFixed(1)}} h · REM ${{q.rem.toFixed(1)}} h`],efficiencyChart:[DATA.efficiency,'#168f5b',' index',null],bodyBatteryChart:[DATA.bodyBattery,'#2774df','',null],stressChart:[DATA.stress,'#ff8b2c','',null],sleepScoreChart:[DATA.sleepScore,'#7157db','',null],spo2Chart:[DATA.spo2,'#168f5b','%',null]}};bars('distanceChart','distance','#ed4337',' km');bars('loadChart','load','#ff8b2c',' load');Object.entries(cfg).forEach(([id,c])=>line(id,...c,90));line('weightChart',DATA.weight,'#168f5b',' kg',365);document.querySelectorAll('.range').forEach(g=>g.onclick=e=>{{if(e.target.tagName!='BUTTON')return;g.querySelectorAll('button').forEach(b=>b.classList.remove('active'));e.target.classList.add('active');line(g.dataset.id,...cfg[g.dataset.id],Number(e.target.dataset.days))}});</script></body></html>'''
doc=doc.replace("Object.entries(cfg).forEach(([id,c])=>line(id,...c,90))","Object.entries(cfg).forEach(([id,c])=>line(id,c[0],c[1],c[2],90,c[3]))")
doc=doc.replace("line(g.dataset.id,...cfg[g.dataset.id],Number(e.target.dataset.days))","(()=>{let c=cfg[g.dataset.id];line(g.dataset.id,c[0],c[1],c[2],Number(e.target.dataset.days),c[3])})()")
status_css="""<style>
.refresh-state{display:flex!important;flex-direction:column;line-height:1.2;text-align:right;font-weight:800;font-size:.7rem}.refresh-state small{font-size:.6rem;color:var(--green)}
.refresh-toast{position:fixed;right:18px;top:76px;z-index:30;background:var(--ink);color:white;border-radius:12px;padding:12px 15px;box-shadow:0 12px 35px #0004;opacity:0;transform:translateY(-10px);pointer-events:none;transition:.22s;max-width:320px;font-weight:800}.refresh-toast.show{opacity:1;transform:translateY(0)}.refresh-btn.spinning{background:var(--blue)}
.insight-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.insight{background:white;border:1px solid var(--line);box-shadow:var(--shadow);border-radius:15px;padding:16px;min-width:0}.insight.primary{background:linear-gradient(145deg,#17202a,#29384a);color:white}.insight.wide{grid-column:span 2}.insight small,.training-card>small{display:block;text-transform:uppercase;letter-spacing:.06em;font-size:.66rem;font-weight:900;color:var(--muted)}.insight.primary small{color:#b9c6d6}.insight strong{display:block;font-size:1.35rem;line-height:1.2;margin:8px 0;overflow-wrap:anywhere}.insight span{display:block;color:var(--muted);font-size:.76rem}.insight.primary span{color:#d3dbe5}
.training-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:11px}.training-card{padding:18px;border-radius:16px}.training-card.wide{grid-column:span 2}.training-card>strong{display:block;font-size:1.45rem;line-height:1.25;margin:8px 0}.training-card p{font-size:.8rem;color:var(--muted);margin:8px 0 0}.stack{height:13px;display:flex;overflow:hidden;border-radius:99px;background:#e9edf2;margin:14px 0 9px}.stack>i{display:block;min-width:0}.stack-legend{display:flex;gap:12px;flex-wrap:wrap;font-size:.72rem;color:var(--muted)}.stack-legend span{display:flex;align-items:center;gap:5px}.stack-legend i{width:8px;height:8px;border-radius:50%;display:inline-block}.stack-legend.compact{gap:9px}.solo{margin-top:12px}.health-charts{margin-top:12px}.missing-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.missing-grid article{background:#fff8ec;border:1px solid #f2dfbb;border-radius:14px;padding:15px}.missing-grid p{color:var(--muted);font-size:.78rem;margin:6px 0 0}
.week-navigator{display:grid;grid-template-columns:auto minmax(220px,1fr) auto auto;align-items:center;gap:10px;background:#17202a;color:white;border-radius:16px;padding:12px 14px;margin-bottom:11px;box-shadow:var(--shadow)}.week-navigator>button{border:0;border-radius:10px;background:#ffffff18;color:white;font-weight:900;min-height:42px;padding:0 14px;cursor:pointer}.week-navigator>button:hover:not(:disabled){background:#ffffff2b}.week-navigator>button:disabled{opacity:.35;cursor:not-allowed}.week-navigator .current-week-btn{background:white;color:var(--ink);white-space:nowrap}.week-slider>div{display:flex;justify-content:space-between;gap:12px;margin-bottom:5px;font-size:.76rem}.week-slider span{color:#b9c6d6}.week-slider input{width:100%;accent-color:var(--red);cursor:pointer}.week-recap{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:11px}.week-recap article{background:#edf5ff;border:1px solid #d5e6fb;border-radius:14px;padding:13px 15px}.week-recap small,.week-recap strong,.week-recap span{display:block}.week-recap small{text-transform:uppercase;color:var(--blue);font-size:.65rem;font-weight:900;letter-spacing:.05em}.week-recap strong{margin:4px 0;font-size:.92rem}.week-recap span{color:var(--muted);font-size:.74rem}
.insight-notice{display:flex;gap:8px;align-items:flex-start;background:#fffbea;border:1px solid #eedf9c;border-radius:14px;padding:13px 15px;margin-bottom:12px}.insight-notice b{white-space:nowrap}.insight-notice span{color:var(--muted)}.coach-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.pattern-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.coach-card{background:white;border:1px solid var(--line);border-top:5px solid #8c98a5;border-radius:16px;box-shadow:var(--shadow);padding:18px;min-width:0;display:flex;flex-direction:column}.coach-card.positive{border-top-color:var(--green)}.coach-card.warning{border-top-color:var(--orange)}.coach-card.priority{border-top-color:var(--blue);background:linear-gradient(180deg,#f5f9ff,#fff 38%)}.coach-card header span{display:block;text-transform:uppercase;letter-spacing:.08em;font-size:.66rem;font-weight:900;color:var(--muted)}.coach-card header b{display:block;font-size:1.15rem;line-height:1.25;margin-top:5px}.coach-card>p{color:var(--muted);font-size:.82rem;margin:9px 0 12px}.coach-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px}.coach-metrics>div{background:#f6f8fb;border:1px solid #e9edf2;border-radius:11px;padding:10px;min-width:0}.coach-metrics small,.coach-metrics strong,.coach-metrics span{display:block}.coach-metrics small{text-transform:uppercase;font-size:.61rem;font-weight:900;color:var(--muted)}.coach-metrics strong{font-size:1.18rem;margin:3px 0;overflow-wrap:anywhere}.coach-metrics span{font-size:.68rem;color:var(--muted)}.coach-action{background:#fffbea;border:1px solid #eee1a9;border-radius:11px;padding:11px 12px;margin-top:11px}.coach-action small,.coach-action strong{display:block}.coach-action small{text-transform:uppercase;letter-spacing:.06em;font-size:.6rem;font-weight:900;color:#8a6b00}.coach-action strong{font-size:.78rem;margin-top:3px}.coach-card footer{color:var(--muted);font-size:.66rem;border-top:1px solid var(--line);padding-top:9px;margin-top:11px}.paired-table{width:100%;border-collapse:collapse;margin-top:11px;font-size:.7rem}.paired-table th,.paired-table td{padding:5px 7px;border-bottom:1px solid var(--line);text-align:right}.paired-table th:first-child{text-align:left}.paired-table thead th{color:var(--muted);text-transform:uppercase;font-size:.58rem}.subhead{display:flex;align-items:end;justify-content:space-between;gap:16px;margin:25px 0 12px}.subhead h3{font-size:1.35rem;margin:2px 0 0}.subhead p{color:var(--muted);margin:0;text-align:right;font-size:.8rem}
@media(max-width:1000px){.nav a{display:none}.insight-grid{grid-template-columns:repeat(2,1fr)}.training-grid{grid-template-columns:repeat(2,1fr)}.missing-grid{grid-template-columns:repeat(2,1fr)}.pattern-grid{grid-template-columns:1fr 1fr}}
@media(max-width:720px){.coach-grid{grid-template-columns:1fr}.insight-notice{display:block}.insight-notice b{display:block;margin-bottom:3px}.subhead{display:block}.subhead p{text-align:left;margin-top:4px}}
@media(max-width:620px){.insight-grid,.training-grid,.missing-grid,.pattern-grid{grid-template-columns:1fr}.insight.wide,.training-card.wide{grid-column:auto}.refresh-state{max-width:112px;font-size:.62rem}.refresh-state small{font-size:.54rem}.refresh-btn{padding:8px 9px}.health-grid{grid-template-columns:1fr 1fr}.week-navigator{grid-template-columns:auto 1fr auto}.week-navigator .current-week-btn{grid-column:1/-1}.week-recap{grid-template-columns:1fr}.week-summary{grid-template-columns:auto 1fr}.recovery-now{grid-column:1/-1;text-align:left}}
@media(max-width:420px){.health-grid{grid-template-columns:1fr}.nav b{font-size:.78rem}.nav-actions{gap:6px!important}.refresh-state{max-width:90px;font-size:.56rem}.refresh-btn{font-size:.72rem}}
</style>"""
doc=doc.replace('</head>',status_css+'</head>')
week_script='''<script>
const weekHistory=DATA.weekHistory||[],weekSlider=document.getElementById('weekSlider'),weekPrev=document.getElementById('weekPrev'),weekNext=document.getElementById('weekNext'),weekCurrent=document.getElementById('weekCurrent');
const weekEsc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const weekSigned=(value,decimals=0,suffix='')=>`${value>=0?'+':''}${Number(value).toFixed(decimals)}${suffix}`;
const weekDayCard=day=>`<article class="day ${weekEsc(day.status)}"><header><div><small>${weekEsc(day.weekday)}</small><strong>${weekEsc(day.dateLabel)}</strong></div><span class="day-score">${day.score==null?'—':day.score}</span></header><div class="effect">${weekEsc(day.effect)}</div><p>${weekEsc(day.why)}</p><div class="day-metrics"><span><b>${Number(day.km).toFixed(1)}</b> km</span><span><b>${day.load}</b> load</span><span><b>${day.sleep==null?'—':Number(day.sleep).toFixed(1)}</b> sleep h</span></div><footer><span>Est. recovery</span><b>${weekEsc(day.recoveryText)}</b></footer></article>`;
function weekTotalsThrough(days){return days.reduce((sum,day)=>({sessions:sum.sessions+Number(day.sessions||0),km:sum.km+Number(day.km||0),load:sum.load+Number(day.load||0)}),{sessions:0,km:0,load:0})}
function weekRecapMarkup(index,week){
  const prior=weekHistory[index-1],before=weekHistory[index-2];
  if(week.current&&prior){
    const today=new Date(`${DATA.today}T12:00:00`),stage=((today.getDay()+6)%7)+1,priorStage=weekTotalsThrough(prior.days.slice(0,stage));
    const priorChange=before?`${weekSigned(prior.km-before.km,1,' km')} distance · ${weekSigned(prior.load-before.load,0,' load')} vs the week before`:'First comparison week';
    return `<article><small>Last week finished</small><strong>${prior.sessions} sessions · ${prior.km.toFixed(1)} km · ${prior.load} load</strong><span>Score ${prior.score}/100 · ${priorChange}</span></article><article><small>This week so far</small><strong>${week.sessions} sessions · ${week.km.toFixed(1)} km · ${week.load} load</strong><span>Same point last week: ${weekSigned(week.km-priorStage.km,1,' km')} · ${weekSigned(week.load-priorStage.load,0,' load')} · updates after every refresh</span></article>`;
  }
  const comparison=prior?`${weekSigned(week.km-prior.km,1,' km')} distance · ${weekSigned(week.load-prior.load,0,' load')} · ${weekSigned(week.sessions-prior.sessions,0,' sessions')}`:'No earlier comparison in this view';
  return `<article><small>Selected week</small><strong>${week.sessions} sessions · ${week.km.toFixed(1)} km · ${week.load} load</strong><span>Score ${week.score}/100 · ${weekEsc(week.effect)}</span></article><article><small>Change from previous week</small><strong>${comparison}</strong><span>${week.recovery==null?'Recovery coverage unavailable':`Average recovery ${week.recovery}/100`} · Monday–Sunday</span></article>`;
}
function renderTrainingWeek(index,persist=true){
  index=Math.max(0,Math.min(weekHistory.length-1,Number(index)));const week=weekHistory[index];if(!week)return;
  weekSlider.value=String(index);weekPrev.disabled=index===0;weekNext.disabled=index===weekHistory.length-1;weekCurrent.disabled=week.current;
  document.getElementById('weekSliderLabel').textContent=week.current?'Current week':week.rangeLabel;
  document.getElementById('weekSliderCount').textContent=`Week ${index+1} of ${weekHistory.length}`;
  document.getElementById('weekRangeLabel').textContent=`Monday–Sunday · ${week.rangeLabel}`;
  document.getElementById('weekHeading').textContent=week.current?'This week at a glance':`Week of ${week.days[0].dateLabel}`;
  document.getElementById('weekRing').style.setProperty('--score',week.score);document.getElementById('weekScore').textContent=week.score;
  document.getElementById('weekEffect').textContent=week.effect;document.getElementById('weekTotals').textContent=`${week.sessions} sessions · ${week.km.toFixed(1)} km · ${week.load} load. Score = 40% volume, 30% consistency and 30% recovery.`;
  document.getElementById('weekRecoveryLabel').textContent=week.current?'Estimated remaining recovery':'Average recovery that week';
  document.getElementById('weekRecovery').textContent=week.current?week.remainingRecovery:(week.recovery==null?'—':`${week.recovery}/100`);
  document.getElementById('weekDays').innerHTML=week.days.map(weekDayCard).join('');document.getElementById('weekRecap').innerHTML=weekRecapMarkup(index,week);
  document.getElementById('weekCurrentAdvice').hidden=!week.current;if(persist)localStorage.setItem('garminSelectedWeek',week.start);
}
if(weekHistory.length){
  const saved=localStorage.getItem('garminSelectedWeek'),savedIndex=weekHistory.findIndex(week=>week.start===saved),initialIndex=savedIndex>=0?savedIndex:weekHistory.length-1;
  weekSlider.addEventListener('input',event=>renderTrainingWeek(event.target.value));weekPrev.addEventListener('click',()=>renderTrainingWeek(Number(weekSlider.value)-1));weekNext.addEventListener('click',()=>renderTrainingWeek(Number(weekSlider.value)+1));weekCurrent.addEventListener('click',()=>renderTrainingWeek(weekHistory.length-1));renderTrainingWeek(initialIndex,false);
}
</script>'''
doc=doc.replace('</body>',week_script+'</body>')
refresh_script='''<script>
const refreshButton=document.getElementById('refreshButton'),refreshState=document.getElementById('refreshState'),refreshToast=document.getElementById('refreshToast');
refreshButton.addEventListener('click',async()=>{
  if(location.protocol==='file:'){refreshState.textContent='Open with refresh.bat first';alert('For one-click refresh, open the dashboard using refresh.bat. This starts the private local refresh helper.');return}
  const isLocalDashboard=['127.0.0.1','localhost'].includes(location.hostname);
  if(!isLocalDashboard){
    const loadedRefresh=refreshState.textContent.trim();
    refreshButton.disabled=true;refreshButton.classList.add('spinning');refreshButton.textContent='↻ Refreshing…';refreshState.innerHTML='Cloud refresh started…<small>Garmin → Cloudflare Pages</small>';refreshToast.textContent='Pulling the latest Garmin data in the cloud. This normally takes a few minutes…';refreshToast.classList.add('show');
    try{
      const response=await fetch('/api/refresh',{method:'POST'}),result=await response.json();if(!response.ok)throw new Error(result.message||'Cloud refresh could not start');
      const deadline=Date.now()+6*60*1000;
      const check=async()=>{const markup=await fetch('/dashboard.html',{cache:'no-store'}).then(value=>value.text()),match=markup.match(/id="refreshState"[^>]*>Last: ([^<]+)/);if(match&&!loadedRefresh.includes(match[1].trim())){refreshToast.textContent='Cloud refresh complete. Loading the new dashboard…';setTimeout(()=>location.reload(),900);return}if(Date.now()<deadline){setTimeout(check,10000);return}refreshState.innerHTML='Refresh is still processing<small>Check again shortly</small>';refreshToast.textContent='The cloud refresh is taking longer than expected. You can safely reload this page in a few minutes.';refreshButton.disabled=false;refreshButton.classList.remove('spinning');refreshButton.textContent='↻ Check again'};
      setTimeout(check,10000);
    }
    catch(error){refreshState.textContent=error.message;refreshToast.textContent=error.message;refreshButton.disabled=false;refreshButton.classList.remove('spinning');refreshButton.textContent='↻ Try again'}
    return;
  }
  refreshButton.disabled=true;refreshButton.classList.add('spinning');refreshButton.textContent='↻ Refreshing…';refreshState.innerHTML='Refreshing now…<small>Garmin → dashboard</small>';refreshToast.textContent='Connecting to Garmin and pulling the latest data…';refreshToast.classList.add('show');
  try{const response=await fetch('/api/refresh',{method:'POST'}),result=await response.json();if(!response.ok)throw new Error(result.message||'Refresh failed');const when=result.last_success?new Date(result.last_success).toLocaleString([], {dateStyle:'medium',timeStyle:'short'}):'just now';refreshState.innerHTML=`Last: ${when}<small>Auto every 2 hours</small>`;refreshToast.textContent=`Refresh complete · ${when}. Reloading dashboard…`;setTimeout(()=>location.reload(),1400)}
  catch(error){refreshState.textContent=error.message;refreshToast.textContent=error.message;refreshButton.disabled=false;refreshButton.classList.remove('spinning');refreshButton.textContent='↻ Try again'}
});
// Keep an open dashboard in sync with the scheduled two-hour rebuild. The
// selected week is restored by the week navigator after the reload.
if(location.protocol!=='file:'){
  const loadedRefresh=refreshState.textContent.trim();
  setInterval(async()=>{try{const markup=await fetch('/dashboard.html',{cache:'no-store'}).then(response=>response.text()),match=markup.match(/id="refreshState"[^>]*>Last: ([^<]+)/);if(match&&!loadedRefresh.includes(match[1].trim()))location.reload()}catch(error){}},60000);
}
</script>'''
doc=doc.replace('</body>',refresh_script+'</body>')
OUT.write_text(doc,encoding='utf-8');print(f'Dashboard built: {OUT}')

