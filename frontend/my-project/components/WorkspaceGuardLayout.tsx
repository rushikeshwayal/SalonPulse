"use client";
import {WorkspaceProvider} from "@/components/WorkspaceProvider";
import {WorkspaceFrame} from "@/components/WorkspaceFrame";
export default function WorkspaceGuardLayout({children}:{children:React.ReactNode}){return <WorkspaceProvider><WorkspaceFrame>{children}</WorkspaceFrame></WorkspaceProvider>;}
