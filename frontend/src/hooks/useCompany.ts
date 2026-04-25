import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";

export interface Company {
  id: string;
  name: string;
  sector: string | null;
  currency: string;
}

async function fetchCompany(): Promise<Company> {
  return apiFetch<Company>("/companies/me");
}

export function useCompany() {
  return useQuery<Company, Error>({
    queryKey: ["company-me"],
    queryFn: fetchCompany,
    staleTime: 5 * 60 * 1000, // 5 min — changes rarely
  });
}
