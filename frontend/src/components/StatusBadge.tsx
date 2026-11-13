export default function StatusBadge({status}:{status:string}){return <span className={`status ${status.toLowerCase()}`}><i/>{status.replaceAll('_',' ')}</span>}
