# ByteTrack tracker subset

Source: https://github.com/FoundationVision/ByteTrack/tree/d1bf0191adff59bc8fcfeaa0b33d3d1642552a99/yolox/tracker
Copyright (c) 2021 Yifu Zhang. MIT license is included in LICENSE.
Original file hashes: upstream_sha256.json. Only four tracker modules are included; no detector or weights.

Local changes: relative package imports; remove unused torch/cv2 imports; replace deprecated np.float with float; explicit high >= track_thresh and low >= low_thresh (0.25) / < track_thresh; preserve input detection index and raw detection tlwh on STrack initialization/update/reactivation for observation provenance. Matching/Kalman/lifecycle/deduplication logic is otherwise retained. Upstream's default high > threshold and low >0.1 differ from this documented experiment contract. No output Kalman box is substituted for a measured boundary position.

Dependencies: numpy==2.2.6, scipy==1.15.3, lap==0.5.12, cython-bbox==0.1.5. See ADR-0010 and EXP-0005 for integration and limitations.
