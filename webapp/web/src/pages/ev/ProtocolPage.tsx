/** A hand-written protocol `/protocol/:name` (evidence/protocols/<name>.yaml). */
import { useParams } from "react-router"

import { useProtocol } from "@/api/ev"
import { QueryPage } from "@/components/ev/bits"
import { ProtocolPanel } from "@/components/ev/ProtocolPanel"
import { PageHeader } from "@/components/layout/PageHeader"

export default function ProtocolPage() {
  const { name = "" } = useParams()
  const protocol = useProtocol(name)
  return (
    <QueryPage query={protocol} what={`protocol ${name}`} back={{ to: "/protocol", label: "All protocols" }}>
      {(view) => (
        <div className="space-y-4">
          <PageHeader title={<span className="font-mono">{view.name}</span>} description="Hand-written, run by the engine as it stands." />
          <ProtocolPanel view={view} />
        </div>
      )}
    </QueryPage>
  )
}
