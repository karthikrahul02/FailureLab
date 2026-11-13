import {FlaskConical} from 'lucide-react'
export default function EmptyState({title='No experiments yet',description='Run your first controlled failure experiment to see resilience metrics here.'}:{title?:string;description?:string}){return <div className="empty"><i><FlaskConical size={23}/></i><b>{title}</b><p>{description}</p></div>}
