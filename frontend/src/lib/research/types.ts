export type ResearchHttpMethod = "GET" | "POST" | "DELETE";

export interface ResearchErrorResponse {
  code: string;
  request_id?: string;
}

export interface CompanySearchItem {
  symbol: string;
  name: string;
  exchange: string | null;
}

export interface CompanySearchResponse {
  items: CompanySearchItem[];
  count: number;
}

export interface WatchlistItem extends CompanySearchItem {
  price: string | null;
  trailing_pe: string | null;
  added_at: string;
}

export interface WatchlistResponse {
  items: WatchlistItem[];
  count: number;
}
