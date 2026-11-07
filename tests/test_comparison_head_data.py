import copy
import unittest
from scripts.prepare_comparison_head_data import window_for


class HeadInputTests(unittest.TestCase):
    def case(self,label=0):
        action='stand' if label==0 else 'wall_over'
        row=dict(time_base='1/3',sample_pts_ticks=list(range(10,18)),sample_frame_indices=list(range(10,18)),
                 actor_id=0,object_id=4,action_class=action,label=label,source_width=100,source_height=80,
                 event_index=0,clip_id='clip')
        annotations=[dict(actor_id=0,object_id=4,class_name=action,cur_frame=i,bbox=[[10,10],[30,70]]) for i in range(10,19)]
        value=dict(annotations=annotations,events=[dict(actor_id=0,object_id=4,ev_start_frame=9,ev_end_frame=20)])
        return row,value

    def test_low_fps_repeats_are_not_sixteen_observations(self):
        row,label=self.case();w=window_for(row,label)
        self.assertEqual(len(w['sample_frame_indices']),16)
        self.assertEqual(w['observed_unique_frames'],7)
        self.assertEqual(sum(w['duplicate_mask']),9)
        self.assertEqual(w['available_after_pts'],16/3)
        self.assertEqual(w['target']['anchor_boxes_origin0_origin1'],[[[10,10],[30,70]]]*2)

    def test_concurrent_other_person_wall_rejects_negative(self):
        row,label=self.case()
        label['annotations'].append(dict(actor_id=1,object_id=5,class_name='wall_over',cur_frame=12,bbox=[[60,10],[80,70]]))
        with self.assertRaisesRegex(ValueError,'source_wide_wall_annotation_conflict'):window_for(row,label)
        label['annotations'][-1]['cur_frame']=2
        label['events'].append(dict(actor_id=1,object_id=5,ev_start_frame=8,ev_end_frame=18))
        with self.assertRaisesRegex(ValueError,'source_wide_wall_event_conflict'):window_for(row,label)

    def test_missing_duplicate_and_wrong_actor_annotations_are_not_normal(self):
        row,label=self.case()
        for mode in ('missing','duplicate','other_actor','conflict'):
            v=copy.deepcopy(label)
            if mode=='missing':v['annotations'].pop(2)
            if mode=='duplicate':v['annotations'].append(v['annotations'][2])
            if mode=='other_actor':v['annotations'][2]['actor_id']=1
            if mode=='conflict':v['annotations'][2]['class_name']='wall_over'
            with self.assertRaisesRegex(ValueError,'ambiguous'):window_for(row,v)

    def test_nonfinite_or_inverted_boxes_rejected(self):
        row,label=self.case(1)
        for b in ([[10,10],[float('nan'),70]],[[30,10],[10,70]],[[10,10],[130,70]]):
            v=copy.deepcopy(label);v['annotations'][2]['bbox']=b
            with self.assertRaisesRegex(ValueError,'invalid_selected_actor_box'):window_for(row,v)



class HeadV2Tests(unittest.TestCase):
    def test_target_keeps_own_alternate_source_and_label_provenance(self):
        row,label=HeadInputTests().case(1)
        row.update(source_id='alias',source_path='/alias.mp4',source_sha256='a'*64,label_path='/alias.json',label_sha256='b'*64)
        target=window_for(row,label)['target']
        for key in ('source_id','source_path','source_sha256','label_path','label_sha256'):
            self.assertEqual(target[key],row[key])
        self.assertEqual(target['source_clip_id'],'clip')
        self.assertEqual(target['anchor_frame_index'],13)

    def test_smoke_is_deterministic_stratified_and_never_test(self):
        from scripts.prepare_comparison_head_data import select_smoke
        rows=[]
        for split,n in [('train',80),('validation',20),('test',10)]:
            for i in range(n):
                rows.append(dict(window_id=split+str(i),split=split,label=i%2,source_sha256=str(i//2),targets=[dict(action_class='wall' if i%2 else 'sit')]))
        selected=select_smoke(rows)
        self.assertEqual(selected,select_smoke(list(reversed(rows))))
        self.assertEqual(len(set(selected)),40)
        chosen=[r for r in rows if r['window_id'] in selected]
        self.assertEqual(sum(w['split']=='train' for w in chosen),32)
        self.assertEqual(sum(w['split']=='validation' for w in chosen),8)
        self.assertFalse(any(w['split']=='test' for w in chosen))
        for split in ('train','validation'):self.assertEqual({w['label'] for w in chosen if w['split']==split},{0,1})

    def test_real_synthetic_pyav_seek_native_pts_and_seven_images(self):
        import tempfile
        from pathlib import Path
        import av
        import numpy as np
        from fractions import Fraction
        from scripts.prepare_comparison_head_data import window_pixels
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'threefps.mkv'
            with av.open(str(path),'w') as container:
                stream=container.add_stream('ffv1',rate=3);stream.width=16;stream.height=16;stream.pix_fmt='bgr0'
                for i in range(12):
                    frame=av.VideoFrame.from_ndarray(np.full((16,16,3),i,dtype=np.uint8),format='rgb24')
                    for packet in stream.encode(frame):container.mux(packet)
                for packet in stream.encode():container.mux(packet)
            with av.open(str(path)) as container:
                frames=list(container.decode(video=0));ticks=[f.pts for f in frames];tb=str(frames[0].time_base)
            indices=[2,3,3,3,4,4,5,5,5,6,6,7,7,7,8,8]
            w=dict(window_id='w',time_base=tb,source_size=[16,16],sample_frame_indices=indices,
                   sample_pts_ticks=[ticks[i] for i in indices],sample_pts=[float(ticks[i]*Fraction(tb)) for i in indices])
            seen=[];result=list(window_pixels(path,[w],lambda tick,rgb:seen.append(tick)))
            self.assertEqual(len(seen),7)
            self.assertEqual(result[0][1][:,0,0,0].tolist(),indices)
            bad=copy.deepcopy(w);bad['sample_pts_ticks'][0]+=1;bad['sample_pts'][0]+=float(Fraction(tb))
            with self.assertRaisesRegex(ValueError,'Missing (selected|requested)'):list(window_pixels(path,[bad]))


if __name__=='__main__':unittest.main()
