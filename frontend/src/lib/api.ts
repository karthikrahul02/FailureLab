import axios from 'axios'
const baseURL=import.meta.env.VITE_API_BASE_URL||'http://localhost:8000/api/v1'
export const api=axios.create({baseURL,timeout:15000})
api.interceptors.request.use(config=>{
  const token=sessionStorage.getItem('failurelab_token')
  if(token) config.headers.Authorization=`Bearer ${token}`
  const apiKey=import.meta.env.VITE_API_KEY
  if(apiKey) config.headers['X-API-Key']=apiKey
  return config
})
export const apiError=(error:unknown)=>axios.isAxiosError(error)?(error.response?.data?.detail||error.message):'An unexpected error occurred.'
