PlantUML and Diagram-as-Code guidance

- Use PlantUML DSL for class diagrams: `class A { +field: type }`
- Prefer explicit visibility (`+/-/#`) and short method signatures
- Ensure no external resources are fetched during rendering (no URLs)
- Render dimensions should fit A4 printable area; export PNG at 300 DPI

When instructing an LLM to generate PlantUML, always require the output inside a fenced block
```puml
...plantuml code...
```
