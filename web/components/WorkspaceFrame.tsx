"use client";
import Link from "next/link";
import {usePathname,useRouter} from "next/navigation";
import {Bell,ChevronDown,ClipboardList,Clock3,LayoutDashboard,LogOut,MessageSquareText,Scissors,UsersRound,Wallet} from "lucide-react";
import {useEffect,useState} from "react";
import {api} from "@/lib/api";
import {useWorkspace} from "@/components/WorkspaceProvider";
type NavItem={href:string;label:string;icon:typeof LayoutDashboard};
export function WorkspaceFrame({children}:{children:React.ReactNode}){
 const {user,data,loading,error}=useWorkspace();const router=useRouter();const pathname=usePathname();const [profileOpen,setProfileOpen]=useState(false);const [notificationCount,setNotificationCount]=useState(0);
 useEffect(()=>{if(user?.role==="barber")api<{count:number}>("/api/notifications?limit=100").then((r)=>setNotificationCount(r.count||0)).catch(()=>setNotificationCount(0));},[user]);
 useEffect(()=>{if(!user)return;if(pathname.startsWith("/owner")&&user.role!=="owner")router.replace("/barber");if(pathname.startsWith("/barber")&&user.role!=="barber")router.replace("/owner");},[pathname,router,user]);
 const owner=user?.role==="owner";
 const ownerNav:NavItem[]=[
 {href:"/owner",label:"Overview",icon:LayoutDashboard},{href:"/owner/visits",label:"Customer visits",icon:ClipboardList},{href:"/owner/customers",label:"Customers",icon:UsersRound},{href:"/owner/feedback",label:"Feedback",icon:MessageSquareText},{href:"/owner/finance",label:"Finance",icon:Wallet},{href:"/owner/audit",label:"Audit log",icon:Clock3}];
 const barberNav:NavItem[]=[
 {href:"/barber",label:"Overview",icon:LayoutDashboard},{href:"/barber/visits",label:"Customer visits",icon:ClipboardList},{href:"/barber/customers",label:"Customers",icon:UsersRound},{href:"/barber/notifications",label:"Notifications",icon:Bell}];
 const nav=owner?ownerNav:barberNav;
 function signOut(){sessionStorage.removeItem("salonpulse_token");router.replace("/login");}
 if(loading||!user||!data)return <main className="loading-screen"><span className="loading-mark"><Scissors size={21}/></span><p>Preparing your workspace…</p>{error?<p className="alert-error">{error}</p>:null}</main>;
 return <div className="app-shell">
  <header className="app-header">
   <Link href={owner?"/owner":"/barber"} className="brand-lockup"><span className="brand-mark"><Scissors size={20}/></span><span><strong>SalonPulse</strong><small>Customer experience workspace</small></span></Link>
   <div className="header-actions"><span className="role-chip">{owner?"OWNER WORKSPACE":"BARBER WORKSPACE"}</span>
    <div className="profile-wrap"><button className="profile-trigger" type="button" onClick={()=>setProfileOpen((open)=>!open)} aria-expanded={profileOpen} aria-label="Open account menu"><span className="profile-icon"><UsersRound size={19}/></span><span className="profile-name">{user.display_name||user.username}</span><ChevronDown size={15}/></button>
    {profileOpen?<div className="profile-menu"><div className="profile-menu-person"><span className="profile-menu-avatar">{(user.display_name||user.username||"U").split(/\s+/).slice(0,2).map((part)=>part.charAt(0)).join("").toUpperCase()}</span><span><strong>{user.display_name||user.username}</strong><small>{user.email}</small></span></div>
    <div className="profile-menu-row"><span>Username</span><strong>{user.username}</strong></div><div className="profile-menu-row"><span>Role</span><strong>{owner?"Owner":"Barber"}</strong></div>
    {!owner?<div className="profile-menu-row"><span>Assigned branch</span><strong>{data.branches[0]?.name?.replace("The Gentlemen's Club — ","")||"Assigned branch"}</strong></div>:null}
    <button className="profile-signout" type="button" onClick={signOut}><LogOut size={16}/> Sign out</button></div>:null}</div>
   </div>
  </header>
  <div className="workspace-container">
   <nav className="workspace-nav" aria-label="Workspace pages">{nav.map((item)=>{const Icon=item.icon;const active=item.href===(owner?"/owner":"/barber")?pathname===item.href:pathname===item.href||pathname.startsWith(item.href+"/");
    return <Link key={item.href} href={item.href} aria-current={active?"page":undefined} className={active?"workspace-tab active":"workspace-tab"}><span className="workspace-tab-icon"><Icon size={17}/>{item.href.endsWith("/notifications")&&notificationCount>0?<span className="notification-badge">{notificationCount>99?"99+":notificationCount}</span>:null}</span><span>{item.label}</span></Link>;})}</nav>
   <main className="workspace-content">{children}</main><footer className="app-footer">SalonPulse · Prototype · Customer messaging is mock-only</footer>
  </div>
 </div>;
}
