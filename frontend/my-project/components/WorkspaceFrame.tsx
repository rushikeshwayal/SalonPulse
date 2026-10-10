"use client";
import Link from "next/link";
import {usePathname,useRouter} from "next/navigation";
import {Bell,ClipboardList,Clock3,LayoutDashboard,LogOut,MessageSquareText,Scissors,UsersRound,Wallet,X} from "@/components/icons";
import {useEffect,useState} from "react";
import {api} from "@/lib/api";
import {useWorkspace} from "@/components/WorkspaceProvider";
type NavItem={href:string;label:string;icon:typeof LayoutDashboard};
export function WorkspaceFrame({children}:{children:React.ReactNode}){
 const {user,data,loading,error}=useWorkspace();const router=useRouter();const pathname=usePathname();const [profileOpen,setProfileOpen]=useState(false);const [notificationCount,setNotificationCount]=useState(0);
 useEffect(()=>{if(user?.role==="barber")api<{count:number}>("/api/notifications?limit=100").then((r)=>setNotificationCount(r.count||0)).catch(()=>setNotificationCount(0));},[user]);
 useEffect(()=>{if(!user)return;if(pathname.startsWith("/owner")&&user.role!=="owner")router.replace("/barber");if(pathname.startsWith("/barber")&&user.role!=="barber")router.replace("/owner");},[pathname,router,user]);
 useEffect(()=>{if(!profileOpen)return;const onKeyDown=(event:KeyboardEvent)=>{if(event.key==="Escape")setProfileOpen(false);};window.addEventListener("keydown",onKeyDown);return()=>window.removeEventListener("keydown",onKeyDown);},[profileOpen]);
 const owner=user?.role==="owner";
 const ownerNav:NavItem[]=[
 {href:"/owner",label:"Overview",icon:LayoutDashboard},{href:"/owner/visits",label:"Customer visits",icon:ClipboardList},{href:"/owner/customers",label:"Customers",icon:UsersRound},{href:"/owner/feedback",label:"Feedback",icon:MessageSquareText},{href:"/owner/finance",label:"Finance",icon:Wallet},{href:"/owner/audit",label:"Audit log",icon:Clock3}];
 const barberNav:NavItem[]=[
 {href:"/barber",label:"Overview",icon:LayoutDashboard},{href:"/barber/visits",label:"Customer visits",icon:ClipboardList},{href:"/barber/customers",label:"Customers",icon:UsersRound},{href:"/barber/notifications",label:"Notifications",icon:Bell}];
 const nav=owner?ownerNav:barberNav;
 function signOut(){sessionStorage.removeItem("salonpulse_token");setProfileOpen(false);router.replace("/login");}
 const displayName=user?.display_name||user?.username||"User";
 const initials=displayName.split(/\s+/).filter(Boolean).slice(0,2).map((part)=>part.charAt(0)).join("").toUpperCase();
 if(loading||!user||!data)return <main className="loading-screen"><span className="loading-mark"><Scissors size={21}/></span><p>Preparing your workspace…</p>{error?<p className="alert-error">{error}</p>:null}</main>;
 return <div className="app-shell">
  <header className="app-header">
   <Link href={owner?"/owner":"/barber"} className="brand-lockup"><span className="brand-mark"><Scissors size={20}/></span><span><strong>SalonPulse</strong><small>Customer experience workspace</small></span></Link>
   <div className="header-actions"><span className="role-chip">{owner?"OWNER WORKSPACE":"BARBER WORKSPACE"}</span>
    <div className="profile-wrap"><button className="profile-trigger" type="button" onClick={()=>setProfileOpen(true)} aria-haspopup="dialog" aria-expanded={profileOpen} aria-label="Open profile details"><span className="profile-icon"><UsersRound size={19}/></span><span className="profile-name">{displayName}</span></button></div>
   </div>
  </header>
  {profileOpen?<div className="modal-backdrop profile-modal-backdrop" onClick={()=>setProfileOpen(false)}>
   <section className="modal-card profile-details-modal" role="dialog" aria-modal="true" aria-labelledby="profile-dialog-title" onClick={(event)=>event.stopPropagation()}>
    <div className="modal-heading profile-details-heading">
     <div className="profile-details-identity"><span className="profile-menu-avatar profile-details-avatar">{initials||"U"}</span><div><span className="eyebrow">ACCOUNT DETAILS</span><h2 id="profile-dialog-title">{displayName}</h2><p>{user.email||"No email address provided"}</p></div></div>
     <button className="icon-button" type="button" onClick={()=>setProfileOpen(false)} aria-label="Close profile details"><X size={18}/></button>
    </div>
    <div className="profile-details-grid">
     <div className="profile-detail"><span>Display name</span><strong>{user.display_name||"Not provided"}</strong></div>
     <div className="profile-detail"><span>Username</span><strong>{user.username}</strong></div>
     <div className="profile-detail"><span>Email address</span><strong>{user.email||"Not provided"}</strong></div>
     <div className="profile-detail"><span>Role</span><strong>{owner?"Owner":"Barber"}</strong></div>
     {!owner?<div className="profile-detail profile-detail-wide"><span>Assigned branch</span><strong>{data.branches[0]?.name?.replace("The Gentlemen's Club — ","")||"Assigned branch"}</strong></div>:null}
    </div>
    <div className="profile-dialog-footer"><span>Signed in to SalonPulse</span><button className="profile-signout" type="button" onClick={signOut}><LogOut size={16}/> Sign out</button></div>
   </section>
  </div>:null}
  <div className="workspace-container">
   <nav className="workspace-nav" aria-label="Workspace pages">{nav.map((item)=>{const Icon=item.icon;const active=item.href===(owner?"/owner":"/barber")?pathname===item.href:pathname===item.href||pathname.startsWith(item.href+"/");
    return <Link key={item.href} href={item.href} aria-current={active?"page":undefined} className={active?"workspace-tab active":"workspace-tab"}><span className="workspace-tab-icon"><Icon size={17}/>{item.href.endsWith("/notifications")&&notificationCount>0?<span className="notification-badge">{notificationCount>99?"99+":notificationCount}</span>:null}</span><span>{item.label}</span></Link>;})}</nav>
   <main className="workspace-content">{children}</main><footer className="app-footer">SalonPulse · Prototype · Customer messaging is mock-only</footer>
  </div>
 </div>;
}
