# `project.json` format (v1)

Image Blend Studio persists projects as JSON using the following structure:

```json
{
  "format": "image_blend_studio_project",
  "version": 1,
  "layers": [
    {
      "layer_id": "string",
      "name": "Layer Name",
      "source_path": "/absolute/or/relative/path/to/image.png",
      "visible": true,
      "opacity": 1.0,
      "blend_mode": "source_over",
      "branches": [
        {
          "branch_id": "string",
          "name": "Branch Name",
          "enabled": true,
          "opacity": 1.0,
          "blend_mode": "source_over",
          "source_branch_id": null,
          "filter_stack": [
            {
              "filter_key": "grayscale",
              "enabled": true,
              "opacity": 1.0,
              "blend_mode": "replace"
            }
          ]
        }
      ]
    }
  ]
}
```

## Notes

- `format` and `version` are required.
- Each `layer` references image data by `source_path` (saved as a project-relative path when possible).
- `source_branch_id` lets branches build from another branch output.
- Effects are non-destructive and applied in listed order.
