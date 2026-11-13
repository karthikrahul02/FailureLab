export type MetricPoint={timestamp:string;latency_ms:number;error_rate:number;cpu_percent:number;availability_percent:number;queue_depth:number}
export type EventItem={timestamp:string;level:'info'|'warning'|'error'|'success';message:string}
export type Experiment={id:string;name:string;target:string;scenario:string;duration_seconds:number;intensity:number;hypothesis:string;status:string;mode:string;created_at:string;completed_at?:string|null;resilience_score?:number|null;anomaly_score?:number|null;summary?:string|null;findings:string[];recommendations:string[];events:EventItem[];metrics:MetricPoint[]}
export type DashboardSummary={total_experiments:number;completed_experiments:number;running_experiments:number;failed_experiments:number;average_resilience:number;healthy_services:number;mode:string;recent_experiments:Experiment[]}
export type ServiceNode={id:string;name:string;type:string;status:string;cpu:number;latency:number;depends_on:string[]}

export type ComparisonResult={id:string;name:string;scenario:string;target:string;status:string;resilience_score:number|null;anomaly_score:number|null;summary:string|null}
