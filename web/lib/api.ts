export class ApiError extends Error {
  status:number;
  constructor(message:string,status:number){ super(message); this.name="ApiError"; this.status=status; }
}
export async function api<T>(path:string,init:RequestInit={}):Promise<T>{
  const headers=new Headers(init.headers);
  if(init.body&&!headers.has("Content-Type")) headers.set("Content-Type","application/json");
  if(typeof window!=="undefined"){
    const token=sessionStorage.getItem("salonpulse_token");
    if(token&&path!=="/api/auth/login") headers.set("Authorization","Bearer "+token);
  }
  let response:Response;
  try{ response=await fetch(path,{...init,headers,cache:"no-store"}); }
  catch{ throw new ApiError("Could not reach SalonPulse. Check your connection and try again.",0); }
  const payload=await response.json().catch(()=>({})) as {detail?:unknown};
  if(!response.ok){
    let message="Request failed ("+response.status+")";
    if(typeof payload.detail==="string") message=payload.detail;
    else if(Array.isArray(payload.detail)) message=payload.detail.map((x:{msg?:string})=>x.msg||"Invalid input").join(", ");
    throw new ApiError(message,response.status);
  }
  return payload as T;
}
export function money(value:number|null|undefined):string{return "₹"+Number(value||0).toLocaleString("en-IN",{maximumFractionDigits:2});}
export function dateTime(value?:string|null):string{
  if(!value)return "—";const parsed=new Date(value);if(Number.isNaN(parsed.getTime()))return "—";
  return parsed.toLocaleString("en-IN",{day:"2-digit",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit"});
}
export function shortDate(value?:string|null):string{if(!value)return "—";const parsed=new Date(value);return Number.isNaN(parsed.getTime())?"—":parsed.toLocaleDateString("en-IN",{day:"2-digit",month:"short",year:"numeric"});}
export function toLocalDateTimeInput(value?:string|null):string{const date=value?new Date(value):new Date();return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);}
export function fromLocalDateTimeInput(value:string):string{return new Date(value).toISOString();}
