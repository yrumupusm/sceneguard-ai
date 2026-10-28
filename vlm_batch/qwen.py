"""Qwen3-VL-2B baseline; EXP7 processor budget and original frame order."""


class Adapter:
    PROCESSOR_SIZE = {'shortest_edge': 16384, 'longest_edge': 3584000}

    def __init__(self, model_dir, settings):
        import torch
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        self.processor = AutoProcessor.from_pretrained(model_dir, local_files_only=True)
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_dir, local_files_only=True, torch_dtype=torch.bfloat16,
            attn_implementation=settings['attention']).to(settings['device']).eval()

    def prepare(self, rgb, source, prompt, clip_id):
        from transformers.video_utils import VideoMetadata
        captured = []
        processor = self.processor
        original = processor.video_processor.resize

        def resize(images, **kwargs):
            result = original(images, **kwargs)
            captured.append(result.detach().cpu().clone())
            return result

        processor.video_processor.resize = resize
        try:
            messages = [{'role': 'user', 'content': [{'type': 'video'},
                        {'type': 'text', 'text': f'Clip ID: {clip_id}\n' + prompt}]}]
            text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            vm = VideoMetadata(total_num_frames=round(5 * source['fps']), fps=source['fps'],
                               width=1920, height=1080, duration=5.0,
                               frames_indices=source['relative_indices'], video_backend='pyav_preselected')
            inputs = processor(text=[text], videos=[rgb], video_metadata=[vm],
                               do_sample_frames=False,
                               size=self.PROCESSOR_SIZE.copy(), return_tensors='pt')
        finally:
            processor.video_processor.resize = original
        grid = inputs['video_grid_thw'].tolist()
        if grid[0][0] * 2 != 10 or len(captured) != 1 or captured[0].shape[0] != 10:
            raise ValueError('Qwen altered the ten-frame contract')
        frames = captured[0].permute(0, 2, 3, 1).numpy().astype('uint8')
        metadata = dict(video_grid_thw=grid, resized_shape=list(captured[0].shape),
                        resize_calls=len(captured), extra_sampling=False, temporal_padding_frames=0,
                        visual_tokens=int((inputs.input_ids == self.model.config.video_token_id).sum()),
                        input_tokens=int(inputs.input_ids.shape[1]),
                        processor_size=self.PROCESSOR_SIZE.copy(),
                        processor_do_pad=getattr(processor.video_processor, 'do_pad', None),
                        frame_order='original ten frames')
        return inputs, metadata, frames
