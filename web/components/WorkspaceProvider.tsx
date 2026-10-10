"use client";
import {createContext,useCallback,useContext,useEffect,useMemo,useState} from "react";
import {useRouter} from "next/navigation";
import {api} from "@/lib/api";
import type {BootstrapData,StaffUser} from "@/lib/types";
interface WorkspaceState{user:StaffUser|null;data:BootstrapData|null;loading:boolean;error:string;refresh:()=>Promise<void>;setData:(data:BootstrapData)=>void;}
const WorkspaceContext=createContext<WorkspaceState|null>(null);
export function WorkspaceProvider({children}:{children:React.ReactNode}){
 const router=useRouter();const [user,setUser]=useState<StaffUser|null>(null);const [data,setData]=useState<BootstrapData|null>(null);const [loading,setLoading]=useState(true);const [error,setError]=useState("");
 const refresh=useCallback(async()=>{const payload=await api<BootstrapData>("/api/bootstrap");setData(payload);setUser(payload.user);setError("");},[]);
 useEffect(()=>{let active=true;async function initialize(){
  if(!sessionStorage.getItem("salonpulse_token")){router.replace("/login");return;}
  try{const signedIn=await api<StaffUser>("/api/auth/me");if(signedIn.must_change_password){router.replace("/login");return;}
   const payload=await api<BootstrapData>("/api/bootstrap");if(!active)return;setUser(signedIn);setData(payload);
  }catch(cause){if(!active)return;sessionStorage.removeItem("salonpulse_token");setError(cause instanceof Error?cause.message:"Unable to load your workspace.");router.replace("/login");}
  finally{if(active)setLoading(false);}
 } initialize();return()=>{active=false;};},[router]);
 const value=useMemo(()=>({user,data,loading,error,refresh,setData}),[user,data,loading,error,refresh]);
 return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}
export function useWorkspace(){const value=useContext(WorkspaceContext);if(!value)throw new Error("useWorkspace must be used inside WorkspaceProvider");return value;}
