import {Outlet,useLocation} from 'react-router-dom'
import {Bell,LogOut} from 'lucide-react'
import Sidebar from './Sidebar'
import {useAuth} from '../context/AuthContext'
const names:Record<string,string>={'/':'Overview','/infrastructure':'Infrastructure map','/experiments':'Experiments','/compare':'Compare experiments'}
export default function Layout(){const location=useLocation();const {user,signOut}=useAuth();return <div className="app-shell"><Sidebar/><main className="main-area"><header className="topbar"><div className="breadcrumbs">FailureLab <span>/</span> <b>{names[location.pathname]||'Experiment details'}</b></div><div className="top-actions"><button className="icon-button" aria-label="Notifications"><Bell size={17}/></button><div className="profile"><i>{(user||'D')[0].toUpperCase()}</i><span>{user?.split('@')[0]||'demo'}</span><button onClick={signOut} title="Sign out"><LogOut size={15}/></button></div></div></header><div className="page-content"><Outlet/></div></main></div>}
