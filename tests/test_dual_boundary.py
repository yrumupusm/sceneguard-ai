"""Causal dual-boundary contracts. Synthetic measurements are not behavior accuracy."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import unittest

from sceneguard.approach_disappearance import Policy
from sceneguard.dual_boundary import Corridor, PassageState, RULE, EPISODE_SECONDS, validate_decision
from sceneguard.exp0048_application import replay_scoped
from sceneguard.incident_cards import GroupPolicy
from sceneguard.incident_lifecycle import CONFIRMED, SUSPECTED
from sceneguard.mvp_pipeline import RuleBackend, analyze_observations
from sceneguard.portal_births import make_region


def scene():
    return dict(source_size=[1000, 1000], line=[[.45,.2],[.45,.8]],
        inner_line=[[.55,.2],[.55,.8]],
        approach_polygon=[[.3,.1],[.7,.1],[.7,.9],[.3,.9]],
        zones={'outside':[[0,0],[.44,0],[.44,1],[0,1]],
               'inside':[[.56,0],[1,0],[1,1],[.56,1]]},
        directions=['outside_to_inside','inside_to_outside'])


def row(x, i, y=500, t=None):
    return dict(pts=i/10 if t is None else t, frame_index=i, cache_index=0,
        bbox=[(x-35)/1000,(y-130)/1000,(x+35)/1000,(y+70)/1000])


def state(xs, sc=None, y=500):
    s=PassageState(Corridor(sc or scene()))
    for i,x in enumerate(xs): s.step(row(x,i,y))
    return s


def fixture(xs, *, end=None, split=None, second=False, paths=True, source_gap=None):
    sc=scene();fs=[];runs={};segments=[]
    for i,x in enumerate(xs):
        r=row(x,i)
        if source_gap is not None and i>=source_gap:r['pts']+=1.
        b=dict(cache_index=0,bbox=deepcopy(r['bbox']),score=.9,observed=True,
            track_ids=[7],assignment='confirmed_track')
        point_paths=[dict(window_id='w',seed_pts=0.,seed_cache_index=0,seed_track_ids=[7],
            point_ids=[0,1,2,3],points_original_pixels=[[x,480+j*5] for j in range(4)])] if paths else []
        fs.append(dict(frame_index=i,pts=r['pts'],native_pts=round(r['pts']*10),time_base='1/10',
            actual_boxes=[b],point_paths=point_paths,camera_step_pixels=[0.,0.]))
        rid='a' if split is None or i<split else 'b'
        runs.setdefault(rid,[]).append(r)
    if second and split is not None:
        for i in range(split,len(xs)):
            b=deepcopy(fs[i]['actual_boxes'][0]);b['cache_index']=1
            b['bbox']=[v+(.01 if k%2==0 else 0) for k,v in enumerate(b['bbox'])]
            fs[i]['actual_boxes'].append(b)
            runs.setdefault('c',[]).append(dict(row(xs[i]+10,i),cache_index=1,bbox=deepcopy(b['bbox'])))
    if end is not None:
        for i in range(end,len(fs)):fs[i]['actual_boxes']=[]
        runs={rid:[r for r in rs if r['frame_index']<end] for rid,rs in runs.items()}
        runs={rid:rs for rid,rs in runs.items() if rs}
    for rid,rs in runs.items():segments.append(dict(id=rid,raw_id=7,rows=deepcopy(rs)))
    e=dict(event_id='e',decision_time_pts=.1,track_ids=[7],status=SUSPECTED,
        session_id='recording',camera_id='C',gate_id='G',video_id='synthetic',
        source_ref=dict(collection='events',source_pointer='/e'),
        source_event=dict(segment='a',raw_id=7,reason='recent_gate_presence_then_loss'))
    baseline=dict(video_id='synthetic',segments=segments,policy=asdict(Policy()))
    history=dict(video_id='synthetic',events=[e],decisions=[],source_window=[0.,fs[-1]['pts']],policy=asdict(GroupPolicy()))
    region=make_region(sc,'C',sc['approach_polygon'],reference_pts=0.,note='Synthetic test')
    return baseline,history,runs,fs,sc,region


def replay_case(xs, **kwargs):
    b,h,r,f,s,p=fixture(xs,**kwargs);original=deepcopy((b,h,r,f,s,p))
    result,_=replay_scoped(b,h,[],r,f,s,p,confirm_outward_crossings=True,observe_gate_crossings=True)
    assert (b,h,r,f,s,p)==original
    return result


class GeometryTests(unittest.TestCase):
    def test_finite_corridor_and_endcap(self):
        g=Corridor(scene())
        self.assertEqual(g.classify(row(400,0)),'outside')
        self.assertEqual(g.classify(row(500,0)),'corridor')
        self.assertEqual(g.classify(row(600,0)),'inside')
        self.assertIsNone(g.classify(row(500,0,y=900)))
        self.assertEqual(g.intersections((400,900),(600,900)),[])

    def test_reversed_endpoints_same_geometry(self):
        s=scene();s['inner_line'].reverse();g=Corridor(s)
        self.assertTrue(g.inner_reversed)
        self.assertEqual(g.inner,Corridor(scene()).inner)

    def test_bent_inner_polyline_is_not_replaced_by_chord(self):
        s=scene();s['inner_line']=[[.55,.2],[.62,.5],[.55,.8]];g=Corridor(s)
        self.assertEqual(g.classify(row(580,0)),'corridor')
        self.assertEqual(g.classify(row(650,0)),'inside')
        self.assertTrue(g.intersections((580,500),(650,500)))

    def test_revision_accepts_explicit_inner_and_preserves_every_other_field(self):
        from sceneguard.gate_episode_evidence import revised_scene
        original=scene();original.pop('inner_line');selected=scene()
        snapshot=deepcopy((original,selected))
        self.assertEqual(revised_scene(original,selected),selected)
        self.assertEqual((original,selected),snapshot)
        for key,value in [('line',[[.46,.2],[.46,.8]]),('directions',['inside_to_outside'])]:
            bad=deepcopy(selected);bad[key]=value
            with self.assertRaises(ValueError):revised_scene(original,bad)

    def test_invalid_inner_and_self_intersection(self):
        for line in ([],[[.5,.5]],[[.5,.5],[.5,.5]],[[float('nan'),.2],[.5,.8]],[[.4,.8],[.6,.2]]):
            s=scene();s['inner_line']=line
            with self.subTest(line=line),self.assertRaises(ValueError):Corridor(s)

    def test_collinear_backtracking_and_nonadjacent_contact_are_not_simple(self):
        for line in ([[.6,.2],[.6,.7],[.6,.4],[.6,.8]],
                     [[.6,.2],[.65,.5],[.6,.5],[.6,.2],[.6,.8]],
                     [[.45,.3],[.45,.7]]):
            s=scene();s['inner_line']=line
            with self.subTest(line=line),self.assertRaises(ValueError):Corridor(s)
        # Collinear vertices in forward order are a valid reviewed polyline.
        s=scene();s['inner_line']=[[.6,.2],[.6,.4],[.6,.8]]
        self.assertEqual(len(Corridor(s).inner),3)


class PassageTests(unittest.TestCase):
    def test_both_directions_need_opposing_boundary(self):
        xs=[400,410,420,460,490,520,560,570,580]
        a=state(xs).decision(.8);b=state([1000-x for x in xs]).decision(.8)
        self.assertTrue(a['automatic_confirmation']);self.assertTrue(b['automatic_confirmation'])
        self.assertEqual(a['direction'],'outside_to_inside');self.assertEqual(b['direction'],'inside_to_outside')
        self.assertFalse(a['loss_wait_required'])

    def test_two_boundaries_in_one_measured_step_keep_temporal_order_both_ways(self):
        for xs in ([600,600,600,400,400,400],[400,400,400,600,600,600]):
            s=PassageState(Corridor(scene()))
            for i,x in enumerate(xs):
                r=row(x,i);r['bbox'][1]=.2075;r['bbox'][3]=.6575;s.step(r)
            self.assertTrue(s.decision(.5)['automatic_confirmation'])

    def test_boundary_touch_requires_opposite_nonzero_anchors(self):
        s=state([400,410,420,450,480,520,550,550,550])
        self.assertIsNone(s.exit)
        self.assertFalse(s.decision(.8)['automatic_confirmation'])
        # The same finite-path checker protects saved-point occlusion paths.
        g=Corridor(scene());trackers={};hits=[]
        path=[(500,500),(550,500),(550,750),(550,850),(580,850),(580,750)]
        for i,p in enumerate(path):hits.extend(g.advance_path(trackers,p,dict(pts=i/10,frame_index=i)))
        self.assertFalse(any(x['boundary']=='inner' and not x['into_corridor'] for x in hits))

    def test_stationary_jitter_object_proxy_and_lingering(self):
        for xs in ([449,451]*20,[400,410,420]+[460]*30,[400,410,420,460,480]+[540]*30):
            with self.subTest(xs=xs):
                s=state(xs);self.assertFalse(s.decision(s.last['pts'])['automatic_confirmation'])
                self.assertFalse(s.decision(s.last['pts']+1,loss=True,
                    direction=dict(direction='inward',end_pts=s.last['pts']))['automatic_confirmation'])

    def test_origin_retained_through_long_unclassified_corridor(self):
        xs=[400,410,420]+[460+i for i in range(50)]+[530,560,570,580]
        s=state(xs);self.assertEqual(s.origin,'outside')
        self.assertGreater(s.last['pts']-s.origin_refs[0]['pts'],3)
        self.assertTrue(s.decision(s.last['pts'])['automatic_confirmation'])

    def test_long_observed_approach_refreshes_origin_without_truncating_it(self):
        xs=[400]*80+[410,420,460,500,540,560,570,580]
        s=state(xs);self.assertTrue(s.decision(s.last['pts'])['automatic_confirmation'])

    def test_corridor_origin_expires(self):
        s=state([400,410,420,460]);s.step(row(500,4,t=EPISODE_SECONDS+1))
        self.assertIsNone(s.origin);self.assertFalse(s.decision(s.last['pts'])['automatic_confirmation'])

    def test_same_side_return_never_confirms(self):
        s=state([400,410,420,460,500,530,500,460,420,410,400])
        self.assertFalse(s.decision(s.last['pts'])['automatic_confirmation'])

    def test_line_extension_cannot_confirm(self):
        self.assertFalse(state([400,410,420,460,500,540,560,570,580],y=900).decision(.8)['automatic_confirmation'])

    def test_prediction_and_bad_geometry_rejected(self):
        s=PassageState(Corridor(scene()));r=row(400,0);r['observed']=False
        with self.assertRaises(ValueError):s.step(r)
        r=row(400,0);r['bbox'][2]=2
        with self.assertRaises(ValueError):s.step(r)

    def test_size_jump_position_jump_and_gap_cannot_inherit_id_origin(self):
        for kind in ('size','position','gap'):
            s=state([400,410,420]);r=row(560,3)
            if kind=='size':r['bbox']=[.54,.48,.58,.52]
            if kind=='position':r=row(800,3)
            if kind=='gap':r['pts']=1.
            s.step(r)
            self.assertFalse(s.decision(r['pts'])['automatic_confirmation']);self.assertIsNone(s.origin)

    def test_loss_requires_origin_entry_terminal_progress_direction_wait(self):
        s=state([400,410,420,460,490,510,530]);last=s.last['pts']
        d=dict(direction='inward',end_pts=last)
        self.assertFalse(s.decision(last+.9,loss=True,direction=d)['automatic_confirmation'])
        self.assertTrue(s.decision(last+1,loss=True,direction=d)['automatic_confirmation'])
        self.assertFalse(s.decision(last+1,loss=True,direction=dict(direction='outward',end_pts=last))['automatic_confirmation'])
        self.assertFalse(s.decision(last+1,loss=True,direction=d,ambiguous=True)['automatic_confirmation'])
        self.assertFalse(s.decision(last+1,loss=True,direction=d,continuous=False)['automatic_confirmation'])
        for xs in ([500,510,520,530],[400,410,420,440],[400,410,420,460,470,480]):
            z=state(xs);self.assertFalse(z.decision(z.last['pts']+1,loss=True,
                direction=dict(direction='inward',end_pts=z.last['pts']))['automatic_confirmation'])


class IntegrationTests(unittest.TestCase):
    def analyze(self, args):
        b,h,r,f,s,p=args
        return analyze_observations(b,h,f,s,p,
            dict(session_id='recording',camera_id='C',gate_id='G'),'association-regression')

    def test_contiguous_branch_and_merge_preserve_passage_in_both_directions(self):
        # EXP0051 supersedes universal graph-uniqueness refusal: these actual
        # coherent paths cross, irrespective of uncertain person assignment.
        for reverse in (False,True):
            xs=[400,410,420,460,490,520,560,570,580]
            if reverse:xs=[1000-x for x in xs]
            for merge in (False,True):
                for offset in (.04,.004):
                    args=fixture(xs,paths=False)
                    for frame in (args[3][:3] if merge else args[3][3:]):
                        box=deepcopy(frame['actual_boxes'][0]);box['cache_index']=1
                        box['bbox'][0]-=offset;box['bbox'][2]-=offset
                        frame['actual_boxes'].append(box)
                    original=deepcopy(args)
                    out=self.analyze(args)['scoped_lifecycle']
                    with self.subTest(reverse=reverse,merge=merge,offset=offset):
                        self.assertEqual(out['counts']['confirmation_notifications'],1)
                        self.assertEqual(out['events'],args[1]['events'])
                        self.assertTrue(any(a['reason']=='competing_contiguous_actual_box_associations'
                            for a in out['followup_audit']))
                        self.assertEqual(args,original)

    def test_gap_raw_competitor_does_not_erase_supported_moving_point_path(self):
        args=fixture([400,410,420,460,490,510,530,550,570,580,590])
        for frame in args[3][5:8]:frame['actual_boxes']=[]
        for frame in args[3][8:]:
            box=deepcopy(frame['actual_boxes'][0]);box['cache_index']=1
            box['bbox'][0]+=.004;box['bbox'][2]+=.004
            frame['actual_boxes'].append(box)
        out=self.analyze(args)['scoped_lifecycle']
        self.assertEqual(out['counts']['confirmation_notifications'],1)
        decision=next(r['source_decision'] for r in out['resolutions']
            if r.get('confirmation_source')==RULE)
        self.assertTrue(decision['associations'])
        self.assertTrue(decision['associations'][0]['missing_box_interval_is_not_measured_box_path'])

    def test_local_competition_allows_later_candidate_without_confirming_old_one(self):
        args=fixture([400]*7+[460,490,520,560,570,580],paths=False)
        b,h,r,f,s,p=args
        for frame in f[:2]:
            box=deepcopy(frame['actual_boxes'][0]);box['cache_index']=1
            box['bbox'][0]-=.04;box['bbox'][2]-=.04
            frame['actual_boxes'].append(box)
        new=deepcopy(h['events'][0]);new.update(event_id='fresh',decision_time_pts=.6)
        h['events'].append(new)
        h['policy']=asdict(GroupPolicy(gap_seconds=.05,max_span_seconds=10.))
        out=self.analyze(args)['scoped_lifecycle']
        evidence={e['event_id']:e for e in out['evidence']}
        self.assertEqual(evidence['e']['automatic_status'],SUSPECTED)
        self.assertEqual(evidence['fresh']['automatic_status'],CONFIRMED)
        self.assertEqual(out['counts']['confirmation_notifications'],1)

    def test_later_competition_preserves_prior_confirmation_and_causal_prefix(self):
        xs=[400,410,420,460,490,520,560,570,580,590,600]
        prefix=self.analyze(fixture(xs[:9],paths=False))['scoped_lifecycle']
        args=fixture(xs,paths=False)
        for frame in args[3][9:]:
            box=deepcopy(frame['actual_boxes'][0]);box['cache_index']=1
            box['bbox'][0]-=.04;box['bbox'][2]-=.04
            frame['actual_boxes'].append(box)
        out=self.analyze(args)['scoped_lifecycle']
        self.assertEqual(out['evidence'][0]['first_confirmation_pts'],.8)
        self.assertEqual(out['evidence'][0]['automatic_status'],CONFIRMED)
        self.assertEqual(out['counts']['confirmation_notifications'],1)
        self.assertEqual(prefix['timeline'],[t for t in out['timeline'] if t['decision_time_pts']<=.8])

    def test_distant_actual_boxes_do_not_veto_unique_passage_or_change_birth_bookkeeping(self):
        from sceneguard.portal_births import compare_births
        args=fixture([400,410,420,460,490,520,560,570,580],paths=False)
        b,h,r,f,s,p=args
        for frame in f:
            box=deepcopy(frame['actual_boxes'][0]);box['cache_index']=1
            box['bbox'][1]=.02;box['bbox'][3]=.12
            frame['actual_boxes'].append(box)
        self.assertEqual(self.analyze(args)['scoped_lifecycle']['counts']['confirmation_notifications'],1)
        dual=compare_births(f,s,p,'C')
        legacy=deepcopy(s);legacy.pop('inner_line')
        portal=make_region(legacy,'C',legacy['approach_polygon'],reference_pts=0.,note='Synthetic legacy')
        old=compare_births(f,legacy,portal,'C')
        self.assertEqual(dual['observation_runs'],old['observation_runs'])
        self.assertTrue(old['observation_bookkeeping_unchanged'])

    def test_production_backend_and_causal_replay(self):
        args=fixture([400,410,420,460,490,520,560,570,580])
        b,h,r,f,s,p=args
        result=analyze_observations(b,h,f,s,p,
            dict(session_id='recording',camera_id='C',gate_id='G'),'synthetic-run')
        self.assertTrue(result['cards']['dual_boundary_rules_enabled'])
        self.assertEqual(result['scoped_lifecycle']['evidence'][0]['automatic_status'],CONFIRMED)
        self.assertTrue(all(not d['automatic_confirmation'] for d in result['seed_decisions']))
        self.assertEqual(result['cards']['counts']['confirmation_notifications'],1)

    def test_visible_confirmation_without_loss_and_return_is_sticky(self):
        r=replay_case([600,590,580,540,510,480,440,430,420,460,500,550,580])
        self.assertEqual(r['evidence'][0]['automatic_status'],CONFIRMED)
        self.assertEqual(r['evidence'][0]['first_confirmation_pts'],.8)
        self.assertEqual(r['counts']['confirmation_notifications'],1)

    def test_future_prefix_is_identical(self):
        xs=[400,410,420,460,490,520,560,570,580]
        a=replay_case(xs[:8]);b=replay_case(xs)
        self.assertEqual(a['counts']['confirmation_notifications'],0)
        self.assertTrue(all(t['decision_time_pts']>=.8 for t in b['resolutions']))
        self.assertEqual(a['timeline'],[t for t in b['timeline'] if t['decision_time_pts']<=.7])

    def test_legacy_positive_seed_cannot_bypass_corridor_guard(self):
        b,h,r,f,s,p=fixture([400,410,420,460,490,520]+[520]*15)
        h['decisions']=[dict(event_id='e',decision_time_pts=.1,automatic_confirmation=True,
            rule_id='ambiguous_gate_loss_v1')]
        out,_=replay_scoped(b,h,[],r,f,s,p)
        self.assertEqual(out['counts']['confirmation_notifications'],0)
        self.assertEqual(len(out['dual_boundary_audit']['suppressed_legacy_confirmations']),1)

    def test_unique_saved_point_handoff_retains_origin_and_confirms(self):
        xs=[400,410,420,460,490,520,560,570,580]
        r=replay_case(xs,split=5)
        self.assertEqual(r['counts']['confirmation_notifications'],1)
        self.assertEqual(r['followup_counts']['observation_handoffs'],1)
        d=next(x['source_decision'] for x in r['resolutions'] if x['kind']=='preserved_confirmation')
        self.assertTrue(d['associations']);self.assertEqual(d['origin_side'],'outside')

    def test_supported_competing_successors_inherit_but_real_gap_without_points_does_not(self):
        xs=[400,410,420,460,490,520,560,570,580]+[580]*12
        self.assertEqual(replay_case(xs,split=5,second=True)['counts']['confirmation_notifications'],1)
        b,h,r,f,s,p=fixture(xs,split=5,paths=False)
        f[4]['actual_boxes']=[];r['a'].pop()
        b['segments'][0]['rows']=deepcopy(r['a'])
        out,_=replay_scoped(b,h,[],r,f,s,p)
        self.assertEqual(out['counts']['confirmation_notifications'],0)

    def test_recording_end_and_source_gap_are_not_loss(self):
        xs=[400,410,420,460,490,510,530]
        self.assertEqual(replay_case(xs)['counts']['confirmation_notifications'],0)
        r=replay_case(xs+[530]*12,end=7,source_gap=8)
        self.assertEqual(r['counts']['confirmation_notifications'],0)

    def test_loss_uses_one_second_actual_absence_in_both_directions(self):
        for xs in ([400,410,420,460,490,510,530],[600,590,580,540,510,490,470]):
            r=replay_case(xs+[xs[-1]]*15,end=7)
            self.assertEqual(r['evidence'][0]['first_confirmation_pts'],1.6)
            decision=next(x['source_decision'] for x in r['resolutions'] if x['kind']=='preserved_confirmation')
            self.assertEqual(decision['reason'],'origin_entry_progress_and_directed_corridor_loss')
            self.assertTrue(decision['measured_recent_path'])

    def test_real_occlusion_gap_uses_saved_point_path_and_never_bbox_chord(self):
        xs=[400,410,420,460,490,510,530,550,570,580,590]
        b,h,r,f,s,p=fixture(xs,split=8)
        for i in (5,6,7):f[i]['actual_boxes']=[]
        r['a']=[x for x in r['a'] if x['frame_index']<5]
        b['segments'][0]['rows']=deepcopy(r['a'])
        out,_=replay_scoped(b,h,[],r,f,s,p)
        self.assertEqual(out['counts']['confirmation_notifications'],1)
        d=next(x['source_decision'] for x in out['resolutions'] if x['kind']=='preserved_confirmation')
        self.assertEqual(d['exit']['measurement'],'saved_point_path')
        self.assertTrue(d['associations'][0]['missing_box_interval_is_not_measured_box_path'])
        self.assertFalse(any(5<=x['frame_index']<=7 for x in d['passage']['destination_observation_refs']))

    def test_late_origin_can_be_used_without_rewriting_source_or_earlier_timeline(self):
        xs=[400,410,420]+[460]*35+[490,520,560,570,580]
        b,h,r,f,s,p=fixture(xs);h['events'][0]['decision_time_pts']=3.6
        out,_=replay_scoped(b,h,[],r,f,s,p)
        self.assertEqual(out['counts']['confirmation_notifications'],1)
        self.assertEqual(out['events'],h['events'])
        self.assertTrue(all(x['decision_time_pts']>=3.6 for x in out['timeline']))

    def test_outcome_confirms_only_one_latest_linked_incident(self):
        b,h,r,f,s,p=fixture([400,410,420,460,490,520,560,570,580])
        h['policy']=asdict(GroupPolicy(gap_seconds=.05,max_span_seconds=10.))
        old=deepcopy(h['events'][0]);old['event_id']='old';old['decision_time_pts']=0.
        h['events'].insert(0,old)
        out,_=replay_scoped(b,h,[],r,f,s,p)
        evidence={x['event_id']:x for x in out['evidence']}
        self.assertEqual(evidence['old']['automatic_status'],SUSPECTED)
        self.assertEqual(evidence['e']['automatic_status'],CONFIRMED)
        self.assertEqual(out['counts']['confirmation_notifications'],1)

    def test_same_id_gap_requires_same_point_proof_not_numeric_id(self):
        b,h,r,f,s,p=fixture([400,410,420,460,490,520,560,570,580])
        f[5]['actual_boxes']=[];r['a']=[x for x in r['a'] if x['frame_index']!=5]
        b['segments'][0]['rows']=deepcopy(r['a'])
        out,_=replay_scoped(b,h,[],r,f,s,p)
        self.assertEqual(out['counts']['confirmation_notifications'],1)
        for frame in f:frame['point_paths']=[]
        out,_=replay_scoped(b,h,[],r,f,s,p)
        self.assertEqual(out['counts']['confirmation_notifications'],0)

    def test_all_low_level_confirmation_shortcuts_guarded(self):
        from sceneguard.existing_alert_crossing import existing_alert_crossing_decision
        from sceneguard.visible_crossing import visible_crossing_decision
        from sceneguard.outward_crossing import outward_loss_decision
        from sceneguard.gate_episode_evidence import history_decision
        previous=dict(automatic_confirmation=True,status=CONFIRMED,decision_time_pts=0.)
        for fn,args in ((existing_alert_crossing_decision,(previous,[],scene())),
            (visible_crossing_decision,(previous,{},scene())),
            (outward_loss_decision,(previous,{},scene())),(history_decision,(previous,{},scene()))):
            self.assertFalse(fn(*args)['automatic_confirmation'])

    def test_existing_alert_binds_measured_anchors_without_legacy_confirmation(self):
        b,h,r,f,s,p=fixture([400,410,420,460,490,520,560,570,580])
        event=h['events'][0];event['decision_time_pts']=.8
        event['source_ref']['collection']='existing_alerts'
        event['source_event']=dict(track_id=7,emitted_at_pts=.8,observed_pts_before=.2,observed_pts_after=.6)
        snapshot=deepcopy(event)
        out,_=replay_scoped(b,h,[],r,f,s,p)
        self.assertEqual(out['counts']['confirmation_notifications'],1)
        self.assertEqual(out['events'][0],snapshot)
        self.assertTrue(out['binding_audit'][0]['observation_key'])
        event['source_event']['observed_pts_after']=.65
        out,_=replay_scoped(b,h,[],r,f,s,p)
        self.assertEqual(next(e for e in out['evidence'] if e['event_id']=='e')['automatic_status'],SUSPECTED)
        self.assertEqual(out['counts']['confirmation_notifications'],1)
        self.assertEqual(len([e for e in out['events'] if e['source_ref']['collection']=='measured_passage_events']),1)

    def test_production_rejects_predicted_boxes_even_when_id_is_confirmed(self):
        b,h,r,f,s,p=fixture([400,410,420,460,490,520,560,570,580])
        f[5]['actual_boxes'][0]['predicted']=True
        with self.assertRaises(ValueError):replay_scoped(b,h,[],r,f,s,p)

    def test_validator_rejects_missing_or_future_support(self):
        r=replay_case([400,410,420,460,490,520,560,570,580])
        d=next(x['source_decision'] for x in r['resolutions'] if x['kind']=='preserved_confirmation')
        validate_decision(d,.8)
        for key in ('entry','origin_observation_refs','physical_evidence_ref'):
            bad=deepcopy(d);bad.pop(key)
            with self.assertRaises(ValueError):validate_decision(bad,.8)
        bad=deepcopy(d);bad['origin_observation_refs'][0]['pts']=10
        with self.assertRaises(ValueError):validate_decision(bad,.8)


if __name__=='__main__':unittest.main()
