import type { ActivatedTool, AssembledPersona } from '../types'

interface Props {
  tool: ActivatedTool
  personas: AssembledPersona[]
}

export function ToolInstanceView({ tool, personas }: Props) {
  const personaName = (personaId: string) => personas.find((p) => p.persona_id === personaId)?.name ?? '(deleted)'

  return (
    <div className="persona-view">
      <div className="persona-header">
        <div>
          <h2>{tool.name}</h2>
          <p className="muted">tool: {tool.tool_id}</p>
        </div>
      </div>

      {tool.destinations.length > 0 && (
        <dl className="tool-config-list">
          {tool.destinations.map((d, i) => (
            <div key={i} className="tool-config-row">
              <dt className="muted">{personaName(d.persona_id)}</dt>
              <dd>{d.description}</dd>
            </div>
          ))}
        </dl>
      )}

      {Object.keys(tool.config).length > 0 && (
        <dl className="tool-config-list">
          {Object.entries(tool.config).map(([key, value]) => (
            <div key={key} className="tool-config-row">
              <dt className="muted">{key}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}

      <p className="muted">Attach this tool to an assistant from its editor's Tools section to put it to use.</p>
    </div>
  )
}
