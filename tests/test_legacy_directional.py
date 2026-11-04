"""Synthetic causal event tests; no video performance or identity claims."""
from copy import deepcopy
from dataclasses import asdict
import unittest

from sceneguard.approach_disappearance import Policy
from sceneguard.legacy_directional import (BoundaryGate, DirectionalGate,
    loss_appearance_candidates, validate_loss_appearance, RULE)
from sceneguard.mvp_pipeline import analyze_observations, RuleBackend
from sceneguard.portal_births import make_region
from sceneguard.incident_cards import GroupPolicy
from sceneguard.incident_outcome_scope import ScopedIncidentLifecycle
from sceneguard.incident_lifecycle import digest

SCOPE = dict(session_id='synthetic-recording',camera_id='C3',gate_id='door')


def fixture(mirror=False, total=41):
    scene = dict(source_size=[1000,1000],line=[[.4,.2],[.4,.8]],
        inner_line=[[.6,.2],[.6,.5],[.6,.8]],
        zones=dict(inside=[[.61,.1],[.95,.1],[.95,.95],[.61,.95]],
                   outside=[[.05,.1],[.39,.1],[.39,.95],[.05,.95]]),
        approach_polygon=[[.3,.1],[.7,.1],[.7,.9],[.3,.9]],
        directions=['outside_to_inside','inside_to_outside'],occlusions=[])
    def box(x):return [x-.025,.4,x+.025,.6]
    frames=[]; rows=[]
    for i in range(total):
        boxes=[]
        if 10 <= i <= 20:
            x=.73-(i-10)*.01
            if mirror:x=1-x
            b=dict(cache_index=0,score=.9,bbox=box(x),track_ids=[7],observed=True)
            boxes.append(b);rows.append(dict(pts=i/10,frame_index=i,**deepcopy(b)))
        if 25 <= i <= 29:
            b=dict(cache_index=1,score=.9,bbox=box(.37 if not mirror else .63),track_ids=[999],observed=True)
            boxes.append(b)
        frames.append(dict(frame_index=i,pts=i/10,native_pts=i,time_base='1/10',actual_boxes=boxes,
            point_paths=[],camera_step_pixels=[0.,0.]))
    baseline=dict(video_id='synthetic',policy=asdict(Policy()),segments=[dict(id='source',raw_id=7,rows=rows)])
    return baseline,frames,scene


def compute(data):return loss_appearance_candidates(*data,SCOPE,'run')


def ambiguous_fixture(mirror=False, earlier_approach=True):
    """Measured origin and actual loss; no terminal signed motion or flow."""
    b, fs, s = fixture(mirror)
    rows = []
    for i in range(5 if earlier_approach else 10,21):
        x = .63 + max(0,10-i)*.02 if earlier_approach else .63
        if mirror:x = 1-x
        box = dict(cache_index=0,score=.9,bbox=[x-.025,.4,x+.025,.6],
                   observed=True,track_ids=[7])
        fs[i]['actual_boxes'] = [deepcopy(box)]
        rows.append(dict(pts=i/10,frame_index=i,**box))
    b['segments'][0]['rows'] = rows
    return b, fs, s


def competing_fixture(mirror=False, strong_end=21):
    """Separate measured source boxes, one destination context, two clocks."""
    b, fs, s = ambiguous_fixture(mirror)
    strong = dict(id='strong',raw_id=8,rows=[])
    for i in range(strong_end-10,strong_end+1):
        x = .73-(i-(strong_end-10))*.01
        if mirror:x = 1-x
        box = dict(cache_index=2,score=.9,bbox=[x-.025,.15,x+.025,.35],
                   observed=True,track_ids=[8])
        fs[i]['actual_boxes'].append(deepcopy(box))
        strong['rows'].append(dict(pts=i/10,frame_index=i,**box))
    b['segments'].append(strong)
    return b, fs, s


def analyze_fixture(data):
    b, fs, s = data
    region = make_region(s,'C3',s['approach_polygon'],reference_pts=0,note='synthetic')
    bundle = dict(video_id='synthetic',events=[],policy=asdict(GroupPolicy()),
                  source_window=[fs[0]['pts'],fs[-1]['pts']])
    before = deepcopy(data)
    result = analyze_observations(b,bundle,fs,s,region,SCOPE,'run')
    assert data == before
    return result


class LossAppearanceTests(unittest.TestCase):
    def assert_appearance(self, data, count):
        result = analyze_fixture(data)
        decisions = [d for d in result['seed_decisions'] if d['rule_id'] == RULE]
        self.assertEqual(len(decisions), count)
        self.assertEqual(result['cards']['counts']['confirmation_notifications'], count)
        if count:
            self.assertEqual(decisions[0]['destination_first_ref']['pts'], 2.5)
            self.assertEqual(decisions[0]['decision_time_pts'], 3.)
            self.assertFalse(decisions[0]['identity_verified'])
        return result

    def test_prior_corridor_does_not_veto_destination_context_both_directions(self):
        for mirror in (False, True):
            data = fixture(mirror)
            x = .59 if mirror else .41
            data[1][19]['actual_boxes'].append(dict(cache_index=9,score=.9,
                bbox=[x-.025,.4,x+.025,.6],observed=True))
            self.assert_appearance(data, 1)

    def test_prior_qualified_destination_vetoes_both_directions(self):
        for mirror in (False, True):
            data = fixture(mirror)
            data[1][19]['actual_boxes'].append(deepcopy(data[1][25]['actual_boxes'][0]))
            self.assert_appearance(data, 0)

    def test_prior_source_side_overlap_does_not_veto_destination_context(self):
        from sceneguard.gate_episode_evidence import association, EpisodePolicy
        for mirror in (False, True):
            data = fixture(mirror)
            x = .37 if mirror else .63
            box = dict(cache_index=9,score=.9,bbox=[x-.32,.2,x+.32,.6],observed=True)
            self.assertIsNotNone(association(box['bbox'],data[1][25]['actual_boxes'][0]['bbox'],
                                            EpisodePolicy().association_overlap))
            data[1][19]['actual_boxes'].append(box)
            self.assert_appearance(data, 1)

    def test_prior_destination_endcap_does_not_veto_finite_context(self):
        from sceneguard.gate_episode_evidence import association, EpisodePolicy
        for mirror in (False, True):
            data = fixture(mirror)
            for frame in data[1][25:30]:
                frame['actual_boxes'][0]['bbox'][1::2] = [.55,.75]
            prior = deepcopy(data[1][25]['actual_boxes'][0]);prior['bbox'][1::2] = [.65,.85]
            self.assertIsNotNone(association(prior['bbox'],data[1][25]['actual_boxes'][0]['bbox'],
                                            EpisodePolicy().association_overlap))
            data[1][19]['actual_boxes'].append(prior)
            self.assert_appearance(data, 1)

    def test_prior_destination_far_from_gate_does_not_veto_near_context(self):
        from sceneguard.gate_episode_evidence import association, EpisodePolicy
        for mirror in (False, True):
            data = fixture(mirror)
            x = .8 if mirror else .2
            prior = dict(cache_index=9,score=.9,bbox=[x-.19,.4,x+.19,.6],observed=True)
            self.assertIsNotNone(association(prior['bbox'],data[1][25]['actual_boxes'][0]['bbox'],
                                            EpisodePolicy().association_overlap))
            data[1][19]['actual_boxes'].append(prior)
            self.assert_appearance(data, 1)

    def test_current_destination_endcap_stays_invalid_both_directions(self):
        for mirror in (False, True):
            data = fixture(mirror)
            for frame in data[1][25:30]:
                frame['actual_boxes'][0]['bbox'][1::2] = [.65,.85]
            self.assert_appearance(data, 0)

    def test_direct_inner_replay_rejects_nonactual_boxes_with_any_engine(self):
        from sceneguard.exp0048_application import replay_scoped
        from sceneguard.directional_loss import SavedGateDirection
        b, fs, s = fixture()
        events, decisions = compute((b, fs, s))
        history = dict(video_id='synthetic',source_window=[0.,4.],
                       events=events,decisions=decisions,policy=asdict(GroupPolicy()))
        region = make_region(s,'C3',s['approach_polygon'],reference_pts=0,note='synthetic')
        clean, _ = replay_scoped(b,history,[],{},fs,s,region)
        self.assertEqual(clean['counts']['confirmation_notifications'], 1)
        for cache in (0,1):
            for flag, value in (('predicted',True),('observed',False),('confirmed',False)):
                for supplied in (False,True):
                    with self.subTest(cache=cache,flag=flag,supplied=supplied):
                        bad = deepcopy(fs)
                        for frame in bad:
                            for box in frame['actual_boxes']:
                                if box['cache_index'] == cache:box[flag] = value
                        engine = SavedGateDirection(fs,s) if supplied else None
                        with self.assertRaisesRegex(ValueError, 'Only actual observed boxes'):
                            replay_scoped(b,history,[],{},bad,s,region,direction_engine=engine)

    def test_destination_context_keeps_one_second_lookback(self):
        for prior_index, expected in ((14,1),(15,0)):
            data = fixture()
            data[1][prior_index]['actual_boxes'].append(deepcopy(data[1][25]['actual_boxes'][0]))
            self.assert_appearance(data, expected)

    def test_destination_context_keeps_six_second_pair_bound(self):
        for destination_index, expected in ((80,1),(81,0)):
            data = fixture(total=91)
            birth = deepcopy(data[1][25]['actual_boxes'][0])
            for frame in data[1][25:30]:frame['actual_boxes'] = []
            data[1][destination_index]['actual_boxes'].append(birth)
            result = analyze_fixture(data)
            self.assertEqual(result['cards']['counts']['confirmation_notifications'], expected)
            if expected:
                decision = next(d for d in result['seed_decisions'] if d['rule_id'] == RULE)
                self.assertEqual(decision['decision_time_pts'], 8.)

    def test_destination_context_keeps_clock_and_single_source_ownership(self):
        data = fixture();other = deepcopy(data[0]['segments'][0]);other.update(id='other',raw_id=8)
        data[0]['segments'].append(other)
        self.assert_appearance(data, 1)
        data = fixture()
        for frame in data[1][19:]:frame['pts'] += .2;frame['native_pts'] += 2
        for row in data[0]['segments'][0]['rows'][9:]:row['pts'] += .2
        self.assert_appearance(data, 0)

    def test_disconnected_ids_no_points_both_directions(self):
        for mirror in (False,True):
            data=fixture(mirror);before=deepcopy(data);events,decisions=compute(data)
            self.assertEqual(data,before);self.assertEqual(len(decisions),1)
            d=decisions[0];self.assertEqual(d['decision_time_pts'],3.)
            self.assertEqual(d['source_last_ref']['pts'],2.)
            self.assertEqual(d['destination_first_ref']['pts'],2.5)
            self.assertEqual(d['direction'],'outside_to_inside' if mirror else 'inside_to_outside')
            self.assertFalse(d['identity_verified']);self.assertFalse(d['reconstructed_path'])
            self.assertFalse(d['shared_point_lineage_required'])
            validate_loss_appearance(d,events[0],3.)

    def test_negative_conditions(self):
        for case in ('standing','away','no_origin','existing','same_side','gap','eof','wrong_gate','no_destination','bad_clock'):
            b,fs,s=fixture()
            if case in ('standing','away','no_origin','wrong_gate'):
                for n,r in enumerate(b['segments'][0]['rows']):
                    x={'standing':.63,'away':.63+n*.005,'no_origin':.59-n*.002,'wrong_gate':.73-n*.01}[case]
                    bb=[x-.025,.4,x+.025,.6]
                    if case=='wrong_gate':bb=[x-.025,.01,x+.025,.15]
                    r['bbox']=bb;fs[r['frame_index']]['actual_boxes'][0]['bbox']=bb
                if case=='standing':
                    # Continued actual presence is not loss. A stationary
                    # terminal history followed by real loss is tested below.
                    fs[27]['actual_boxes'].append(dict(cache_index=3,score=.9,
                        bbox=deepcopy(b['segments'][0]['rows'][-1]['bbox']),observed=True))
            elif case=='existing':
                fs[19]['actual_boxes'].append(dict(cache_index=1,score=.9,bbox=[.345,.4,.395,.6],observed=True))
            elif case=='same_side':
                for f in fs[25:30]:f['actual_boxes'][0]['bbox']=[.625,.4,.675,.6]
            elif case=='gap':
                for f in fs[22:]:f['pts']+=.3;f['native_pts']+=3
            elif case=='eof':fs=fs[:28]
            elif case=='no_destination':
                for f in fs[25:30]:f['actual_boxes']=[]
            elif case=='bad_clock':b['segments'][0]['rows'][-1]['pts']=1.95
            self.assertEqual(compute((b,fs,s)),([],[]),case)

    def test_source_return_before_decision_rejects(self):
        b,fs,s=fixture();fs[27]['actual_boxes'].append(dict(cache_index=3,score=.9,bbox=[.605,.4,.655,.6]))
        self.assertEqual(compute((b,fs,s)),([],[]))

    def test_source_clock_gap_before_loss_rejects(self):
        b,fs,s=fixture()
        for f in fs[19:]:f['pts']+=.2;f['native_pts']+=2
        for r in b['segments'][0]['rows'][9:]:r['pts']+=.2
        self.assertEqual(compute((b,fs,s)),([],[]))

    def test_same_appearance_not_applied_to_multiple_sources(self):
        b,fs,s=fixture();other=deepcopy(b['segments'][0]);other.update(id='other',raw_id=8)
        b['segments'].append(other)
        self.assertEqual(len(compute((b,fs,s))[0]),1)

    def test_first_origin_not_transferred_from_outside(self):
        b,fs,s=fixture()
        # Historical disconnected origin is not bridged solely by raw ID.
        rows=b['segments'][0]['rows'];rows[2]['frame_index']=rows[1]['frame_index']
        self.assertEqual(compute((b,fs,s)),([],[]))  # invalid source references are not origin evidence
        # Too few actual origin observations cannot prove an inside source.
        b,fs,s=fixture();b['segments'][0]['rows']=b['segments'][0]['rows'][-2:]
        self.assertEqual(compute((b,fs,s)),([],[]))

    def test_bottom_center_and_polyline_without_global_midpoint_change(self):
        from sceneguard.approach_disappearance import center
        _,_,s=fixture();gate=BoundaryGate(s,'inside')
        loc=gate.locate([.61,.1,.65,.6])
        self.assertEqual(loc['center_pixels'],(630.,600.));self.assertEqual(loc['segment'],1)
        self.assertEqual(center({'bbox':[.61,.1,.65,.6]},[1000,1000]),(630.,350.))

    def test_lifecycle_and_activity_sticky_after_later_return(self):
        b,fs,s=fixture(total=61)
        for i in range(41,46):
            fs[i]['actual_boxes']=[dict(cache_index=2,score=.9,bbox=[.625,.4,.675,.6],observed=True)]
        region=make_region(s,'C3',[[.35,.2],[.65,.2],[.65,.8],[.35,.8]],reference_pts=0,note='synthetic')
        bundle=dict(video_id='synthetic',events=[],policy=asdict(GroupPolicy()),source_window=[0.,6.])
        result=analyze_observations(b,bundle,fs,s,region,SCOPE,'run')
        self.assertEqual(len([d for d in result['seed_decisions'] if d['rule_id']==RULE]),1)
        self.assertEqual(result['cards']['counts']['confirmation_notifications'],1)
        self.assertEqual([e['automatic_status'] for e in result['scoped_lifecycle']['evidence']
                          if e['event_id']==result['seed_decisions'][0]['event_id']],['침입 확인'])
        self.assertFalse(result['cards']['release_rule_changed'])
        self.assertFalse(result['cards']['dual_boundary_rules_enabled'])
        self.assertIn(RULE,result['cards']['source_algorithm_versions'])
        self.assertFalse(result['scoped_lifecycle']['source_end_forced_release'])

    def test_lifecycle_rejects_forged_or_future_provenance(self):
        events,decisions=compute(fixture());e,d=events[0],decisions[0]
        for field,value in [('identity_verified',True),('source_clock_continuous',False),('decision_time_pts',3.1)]:
            bad=dict(d,**{field:value})
            with self.assertRaises(ValueError):validate_loss_appearance(bad,e,3.)

    def test_prefix_equivalence_and_later_reused_id_piece(self):
        b,fs,s=fixture(total=71)
        prefix=compute((deepcopy(b),deepcopy(fs[:31]),s))
        for i in range(51,61):
            x=.73-(i-51)*.01
            box=dict(cache_index=2,score=.9,bbox=[x-.025,.4,x+.025,.6],observed=True)
            fs[i]['actual_boxes']=[box]
            b['segments'][0]['rows'].append(dict(pts=i/10,frame_index=i,**deepcopy(box)))
        full=compute((b,fs,s))
        self.assertEqual(prefix,full)
        for length in (21,26,30,31):
            clipped=deepcopy(b)
            clipped['segments'][0]['rows']=[r for r in clipped['segments'][0]['rows'] if r['frame_index']<length]
            got=compute((clipped,fs[:length],s))
            expected=tuple([x for x in values if x['decision_time_pts']<=fs[length-1]['pts']] for values in full)
            self.assertEqual(got,expected)

    def test_bbox_jitter_does_not_reject_aggregate_approach(self):
        b,fs,s=fixture()
        row=b['segments'][0]['rows'][5]
        row['bbox']=[v+.015 if i in (0,2) else v for i,v in enumerate(row['bbox'])]
        fs[row['frame_index']]['actual_boxes'][0]['bbox']=deepcopy(row['bbox'])
        self.assertEqual(len(compute((b,fs,s))[0]),1)

    def test_slow_gate_approach_retains_origin_beyond_three_seconds(self):
        from sceneguard.legacy_directional import retained_origin
        _,_,s=fixture();s['zones']['inside']=[[.75,.1],[.95,.1],[.95,.95],[.75,.95]]
        rows=[dict(pts=i/10,frame_index=i,bbox=[.8-i*.002-.025,.4,.8-i*.002+.025,.6]) for i in range(81)]
        self.assertTrue(retained_origin(rows,s,BoundaryGate(s,'inside'),'inside'))
        rows.extend(dict(pts=i/10,frame_index=i,bbox=[.715,.4,.765,.6]) for i in range(81,121))
        for r in rows[30:]:r['bbox']=[.715,.4,.765,.6]
        self.assertFalse(retained_origin(rows,s,BoundaryGate(s,'inside'),'inside'))

    def test_inside_moving_away_does_not_take_inward_followup_route(self):
        from sceneguard.lifecycle_followup import ObservationHistory,assess_loss
        b,fs,s=fixture();rows=b['segments'][0]['rows']
        history=ObservationHistory({'source':rows},fs)
        for frame in fs[:31]:history.advance(frame)
        class Engine:
            policy=type('Policy',(),dict(history_seconds=1.))()
            def direction(self,segment):return dict(direction='inward',end_pts=2.,source_origin_side='inside')
            def continuation(self,segment,index):return 'unresolved'
        class Portal:
            def locate(self,bbox):return {'inside_birth_site':True}
        self.assertIsNone(assess_loss(history,Engine(),Portal(),'source',30)['outcome'])

    def test_reversed_inner_endpoints_preserve_signed_boundary_meaning(self):
        from sceneguard.legacy_directional import source_scene
        from sceneguard.directional_loss import gate_geometry
        b,fs,s=fixture();normal=compute((b,fs,s))
        before=source_scene(s,'inside',b['segments'][0]['rows'][-1]['bbox'])['line']
        s['inner_line'].reverse()
        after=source_scene(s,'inside',b['segments'][0]['rows'][-1]['bbox'])['line']
        self.assertEqual(before,after)
        reversed_result=compute((b,fs,s))
        self.assertEqual(len(normal[0]),len(reversed_result[0]))
        self.assertEqual(normal[1][0]['direction'],reversed_result[1][0]['direction'])
        from test_existing_alert_crossing import inputs
        from sceneguard.existing_alert_crossing import existing_alert_crossing_decision
        src,segs,sc=inputs(outward=True);sc['inner_line']=[[.51,.25],[.51,.75]]
        forward=existing_alert_crossing_decision(src,segs,sc)
        self.assertTrue(forward['automatic_confirmation'])
        sc['inner_line'].reverse()
        self.assertEqual(existing_alert_crossing_decision(src,segs,sc),forward)

    def test_predicted_source_or_destination_is_not_actual_evidence(self):
        for cache in (0,1):
            for flag,value in (('predicted',True),('confirmed',False),('observed',False)):
                b,fs,s=fixture()
                for frame in fs:
                    for box in frame['actual_boxes']:
                        if box['cache_index']==cache:box[flag]=value
                self.assertEqual(compute((b,fs,s)),([],[]))
                with self.assertRaises(ValueError):DirectionalGate(fs,s)

    def test_malformed_inner_geometry_fails_closed(self):
        for inner in ([],[[.6,.2]],[[.6,.2],[.6,.8],[.6,.4]]):
            _,fs,s=fixture();s['inner_line']=inner
            with self.assertRaises(ValueError):DirectionalGate(fs,s)

    def test_existing_inward_routes_restored_with_inner_line(self):
        from test_visible_crossing import scene, row
        from sceneguard.visible_crossing import visible_crossing_decision
        from sceneguard.outward_crossing import outward_loss_decision
        from test_outward_crossing import inputs
        args=inputs();prior=deepcopy(args[0]);prior.update(automatic_confirmation=True)
        args[2]['inner_line']=[[.6,.2],[.6,.8]]
        self.assertEqual(outward_loss_decision(prior,args[1],args[2]),prior)
        from test_existing_alert_crossing import inputs as alert_inputs
        from sceneguard.existing_alert_crossing import existing_alert_crossing_decision
        src,segs,sc=alert_inputs()
        expected=existing_alert_crossing_decision(src,segs,sc)
        sc['inner_line']=[[.6,.2],[.6,.8]]
        self.assertEqual(existing_alert_crossing_decision(src,segs,sc),expected)

    def test_ambiguous_terminal_after_measured_approach_both_directions(self):
        for mirror in (False,True):
            data = ambiguous_fixture(mirror)
            events, decisions = compute(data)
            self.assertEqual(len(decisions),1)
            d = decisions[0]
            self.assertTrue(d['source_direction_uncertain'])
            self.assertEqual(d['direction_evidence']['direction'],'unknown')
            self.assertEqual(d['confirmation_supplied_by'],
                             'qualified_opposite_boundary_first_appearance')
            self.assertEqual(d['decision_time_pts'],3.)
            self.assertFalse(d['identity_verified'])
            self.assertFalse(d['reconstructed_path'])
            validate_loss_appearance(d,events[0],3.)
            self.assert_appearance(data,1)

    def test_constant_source_with_actual_loss_is_unknown_not_proven_stationary(self):
        # Coordinator clarified that zero motion alone is no veto when the
        # source actually disappears and a qualified opposite appearance follows.
        for mirror in (False,True):
            self.assert_appearance(ambiguous_fixture(mirror,False),1)

    def test_parallel_measured_motion_needs_no_historical_gateward_window(self):
        for mirror in (False,True):
            b, fs, s = ambiguous_fixture(mirror,False)
            for n, row in enumerate(b['segments'][0]['rows']):
                row['bbox'][1::2] = [.3+n*.01,.5+n*.01]
                fs[row['frame_index']]['actual_boxes'][0]['bbox'] = deepcopy(row['bbox'])
            self.assert_appearance((b,fs,s),1)

    def test_ambiguous_fallback_keeps_actual_loss_and_destination_guards(self):
        for mirror in (False,True):
            for case in ('no_destination','retreat','no_origin','source_gap',
                         'eof','existing_destination','endcap','same_side','continued_standing'):
                with self.subTest(mirror=mirror,case=case):
                    b, fs, s = ambiguous_fixture(mirror)
                    if case=='no_destination':
                        for frame in fs[25:30]:frame['actual_boxes']=[]
                    elif case=='retreat':
                        for n,row in enumerate(b['segments'][0]['rows'][5:]):
                            dx = n*.005*(-1 if mirror else 1)
                            row['bbox'] = [v+dx if k in (0,2) else v for k,v in enumerate(row['bbox'])]
                            fs[row['frame_index']]['actual_boxes'][0]['bbox']=deepcopy(row['bbox'])
                    elif case=='no_origin':
                        b['segments'][0]['rows']=b['segments'][0]['rows'][-2:]
                    elif case=='source_gap':
                        for frame in fs[22:]:frame['pts']+=.3;frame['native_pts']+=3
                    elif case=='eof':fs=fs[:28]
                    elif case=='existing_destination':
                        fs[19]['actual_boxes'].append(deepcopy(fs[25]['actual_boxes'][0]))
                    elif case=='endcap':
                        for frame in fs[25:30]:frame['actual_boxes'][0]['bbox'][1::2]=[.65,.85]
                    elif case in ('same_side','continued_standing'):
                        box=deepcopy(fs[20]['actual_boxes'][0]);box['cache_index']=3
                        fs[27]['actual_boxes'].append(box)
                        if case=='same_side':
                            for frame in fs[25:30]:frame['actual_boxes']=[deepcopy(box)]
                    self.assertEqual(compute((b,fs,s)),([],[]))

    def test_ambiguous_single_birth_and_prefixes(self):
        for mirror in (False,True):
            data=ambiguous_fixture(mirror)
            other=deepcopy(data[0]['segments'][0]);other.update(id='other',raw_id=8)
            data[0]['segments'].append(other)
            full=compute(data)
            self.assertEqual(len(full[0]),1)
            for length in (21,26,30,31,41):
                b,fs,s=deepcopy(data)
                fs=fs[:length]
                for seg in b['segments']:
                    seg['rows']=[r for r in seg['rows'] if r['frame_index']<length]
                expected=tuple([x for x in values if x['decision_time_pts']<=fs[-1]['pts']] for values in full)
                self.assertEqual(compute((b,fs,s)),expected)

    def test_same_clock_strong_priority_and_original_evidence_bytes(self):
        for mirror in (False,True):
            data=competing_fixture(mirror,strong_end=20)
            strong_only=deepcopy(data);strong_only[0]['segments']=strong_only[0]['segments'][1:]
            self.assertEqual(compute(data),compute(strong_only))

    def test_original_strong_serialized_outputs_match_frozen_before(self):
        # Entire event/evidence dictionaries, including IDs, from the approved
        # df545f42 frozen source; no newly generated expectation at test time.
        expected = ('c6c86037996d022e6f21900523783980199d25142f74fe4764332bffa8839b7d',
                    '3165fa6cec22d0339ee7fbf43edccf7951b0ff655ac341aeca4fe63abf736ae3')
        for mirror, checksum in zip((False,True),expected):
            self.assertEqual(digest(compute(fixture(mirror))),checksum)

    def test_later_strong_support_preserved_without_rewriting_earlier_auxiliary(self):
        for mirror in (False,True):
            data=competing_fixture(mirror)
            strong_only=deepcopy(data);strong_only[0]['segments']=strong_only[0]['segments'][1:]
            strong=compute(strong_only)
            full=compute(data)
            full_pipeline=analyze_fixture(data)
            self.assertEqual(len(full[0]),2)
            for old,new in zip(strong,full):self.assertEqual(new[1:],old)
            self.assertEqual([d['decision_time_pts'] for d in full[1]],[3.,3.1])
            for length in (30,31,32,41):
                b,fs,s=deepcopy(data);fs=fs[:length]
                for seg in b['segments']:
                    seg['rows']=[r for r in seg['rows'] if r['frame_index']<length]
                expected=tuple([x for x in values if x['decision_time_pts']<=fs[-1]['pts']] for values in full)
                self.assertEqual(compute((b,fs,s)),expected)
                prefix_pipeline=analyze_fixture((b,fs,s))
                for layer in ('cards','scoped_lifecycle'):
                    for key in ('notification_intents','timeline'):
                        expected=[r for r in full_pipeline[layer][key]
                                  if r['decision_time_pts']<=fs[-1]['pts']]
                        self.assertEqual(prefix_pipeline[layer][key],expected)
            self.assertEqual(full_pipeline['cards']['counts']['confirmation_notifications'],1)

if __name__=='__main__':unittest.main()
