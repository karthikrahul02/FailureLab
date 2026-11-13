import type {ReactNode} from 'react'
export default function MetricCard({label,value,hint,icon}:{label:string;value:string|number;hint:string;icon:ReactNode}){return <article className="metric-card"><div className="metric-head"><span>{label}</span><i>{icon}</i></div><strong>{value}</strong><small>{hint}</small></article>}
