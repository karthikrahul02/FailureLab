import {createContext,useCallback,useContext,useMemo,useState} from 'react'
import type {ReactNode} from 'react'
import {AuthenticationDetails,CognitoUser,CognitoUserPool} from 'amazon-cognito-identity-js'
type AuthValue={user:string|null;signIn:(email:string,password:string)=>Promise<void>;signOut:()=>void;demoSignIn:()=>void}
const Context=createContext<AuthValue|null>(null)
const mode=import.meta.env.VITE_AUTH_MODE||'demo'
export function AuthProvider({children}:{children:ReactNode}){
 const [user,setUser]=useState<string|null>(()=>sessionStorage.getItem('failurelab_user'))
 const signIn=useCallback(async(email:string,password:string)=>{
  if(mode==='demo'){sessionStorage.setItem('failurelab_user',email);setUser(email);return}
  const poolId=import.meta.env.VITE_COGNITO_USER_POOL_ID;const clientId=import.meta.env.VITE_COGNITO_CLIENT_ID
  if(!poolId||!clientId)throw new Error('Cognito is not configured. Set the VITE_COGNITO_* variables.')
  const pool=new CognitoUserPool({UserPoolId:poolId,ClientId:clientId});const cognitoUser=new CognitoUser({Username:email,Pool:pool});const details=new AuthenticationDetails({Username:email,Password:password})
  await new Promise<void>((resolve,reject)=>cognitoUser.authenticateUser(details,{onSuccess:session=>{sessionStorage.setItem('failurelab_token',session.getIdToken().getJwtToken());sessionStorage.setItem('failurelab_user',email);setUser(email);resolve()},onFailure:reject,newPasswordRequired:()=>reject(new Error('A new password is required. Reset the account password in Cognito.'))}))
 },[])
 const signOut=useCallback(()=>{sessionStorage.removeItem('failurelab_user');sessionStorage.removeItem('failurelab_token');setUser(null)},[])
 const demoSignIn=useCallback(()=>{if(mode==='demo'){sessionStorage.setItem('failurelab_user','demo@failurelab.local');setUser('demo@failurelab.local')}},[])
 const value=useMemo(()=>({user,signIn,signOut,demoSignIn}),[user,signIn,signOut,demoSignIn])
 return <Context.Provider value={value}>{children}</Context.Provider>
}
export function useAuth(){const value=useContext(Context);if(!value)throw new Error('useAuth must be inside AuthProvider');return value}
