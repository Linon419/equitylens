export type ResearchHttpMethod = "GET" | "POST" | "DELETE";

export interface ResearchErrorResponse {
  code: string;
  request_id?: string;
}
