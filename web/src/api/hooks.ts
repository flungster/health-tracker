/** TanStack Query hooks: the only place components read/write API data. */

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { ApiError, apiRequest } from "./client";
import type {
  ActivitiesListView,
  ActivityDetailView,
  ClientConfigView,
  ConnectUrlView,
  ProfileView,
  ProviderConnectionView,
  ProvidersView,
  SportsView,
  SyncResultView,
  TrackpointsView,
  UserView,
} from "./types";

export function useActivities(limit: number, offset: number) {
  const path = `/api/v1/activities?limit=${limit}&offset=${offset}`;
  return useQuery({
    queryKey: ["activities", limit, offset],
    queryFn: () => apiRequest<ActivitiesListView>(path),
  });
}

const FEED_PAGE_SIZE = 20;

/** Paginated activity feed for "load more". */
export function useActivitiesInfinite() {
  return useInfiniteQuery<ActivitiesListView, Error>({
    queryKey: ["activities", "feed"],
    initialPageParam: 0,
    getNextPageParam: (lastPage) =>
      lastPage.offset + lastPage.limit < lastPage.total
        ? lastPage.offset + lastPage.limit
        : undefined,
    queryFn: ({ pageParam }) =>
      apiRequest<ActivitiesListView>(
        `/api/v1/activities?limit=${FEED_PAGE_SIZE}&offset=${pageParam}`,
      ),
  });
}

export function useActivity(id: string) {
  return useQuery({
    queryKey: ["activity", id],
    queryFn: () => apiRequest<ActivityDetailView>(`/api/v1/activities/${id}`),
  });
}

export function useTrackpoints(id: string) {
  return useQuery({
    queryKey: ["trackpoints", id],
    queryFn: () => apiRequest<TrackpointsView>(`/api/v1/activities/${id}/trackpoints`),
  });
}

export function useSports() {
  return useQuery({
    queryKey: ["sports"],
    queryFn: () => apiRequest<SportsView>("/api/v1/sports"),
  });
}

export function useProfile() {
  return useQuery({
    queryKey: ["profile"],
    queryFn: () => apiRequest<ProfileView>("/api/v1/users/me/profile"),
  });
}

export type ImportInput = {
  file: File;
  sportType: string | null;
  name: string | null;
};

export function useImportActivity() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ImportInput) => {
      const formData = new FormData();
      formData.append("file", input.file);
      if (input.sportType !== null) {
        formData.append("sport_type", input.sportType);
      }
      if (input.name !== null && input.name !== "") {
        formData.append("name", input.name);
      }
      return apiRequest<ActivityDetailView>("/api/v1/activities", {
        method: "POST",
        formData,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["activities"] });
    },
  });
}

export type ActivityUpdateInput = {
  name: string | null;
  description: string | null;
  sport_type: string | null;
};

export function useUpdateActivity(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ActivityUpdateInput) =>
      apiRequest<ActivityDetailView>(`/api/v1/activities/${id}`, {
        method: "PATCH",
        json: input,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["activity", id] });
      void queryClient.invalidateQueries({ queryKey: ["activities"] });
    },
  });
}

export function useDeleteActivity() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiRequest<void>(`/api/v1/activities/${id}`, { method: "DELETE" }),
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({ queryKey: ["activities"] });
      void queryClient.invalidateQueries({ queryKey: ["activity", id] });
    },
  });
}

export type ProfileUpdateInput = {
  max_heart_rate: number | null;
  resting_heart_rate: number | null;
  date_of_birth: string | null; // "YYYY-MM-DD" or null to clear
  custom_zone_1_top_bpm: number | null; // all four or none (server-enforced)
  custom_zone_2_top_bpm: number | null;
  custom_zone_3_top_bpm: number | null;
  custom_zone_4_top_bpm: number | null;
};

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ProfileUpdateInput) =>
      apiRequest<ProfileView>("/api/v1/users/me/profile", { method: "PATCH", json: input }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}

export type UserUpdateInput = {
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  current_password: string | null;
  new_password: string | null;
};

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UserUpdateInput) => apiRequest<UserView>("/api/v1/users/me", {
      method: "PATCH",
      json: input,
    }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

export function useProviders() {
  return useQuery({
    queryKey: ["providers"],
    queryFn: () => apiRequest<ProvidersView>("/api/v1/providers"),
  });
}

export function useProviderConnection(provider: string) {
  return useQuery({
    queryKey: ["provider-connection", provider],
    queryFn: async () => {
      try {
        return await apiRequest<ProviderConnectionView>(
          `/api/v1/providers/${provider}/connection`,
        );
      } catch (error) {
        // 404 means "not connected", which is a normal state, not an error.
        if (error instanceof ApiError && error.status === 404) {
          return null;
        }
        throw error;
      }
    },
  });
}

export function useConnectProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (provider: string) =>
      apiRequest<ConnectUrlView>(`/api/v1/providers/${provider}/connect`),
    onSuccess: (data, provider) => {
      void queryClient.invalidateQueries({ queryKey: ["provider-connection", provider] });
      // Hand the browser to the provider. It redirects back to /profile with
      // ?connected= or ?connect_error=, which the page reports to the user.
      window.location.assign(data.url);
    },
  });
}

export function useDisconnectProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (provider: string) =>
      apiRequest<void>(`/api/v1/providers/${provider}/connection`, { method: "DELETE" }),
    onSuccess: (_data, provider) => {
      void queryClient.invalidateQueries({ queryKey: ["provider-connection", provider] });
    },
  });
}

export function useSyncProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ provider, since }: { provider: string; since?: string }) =>
      apiRequest<SyncResultView>(`/api/v1/providers/${provider}/sync`, {
        method: "POST",
        // No body = use the connection's saved import-from floor (or none).
        json: since !== undefined && since !== "" ? { since } : undefined,
      }),
    onSuccess: (_data, { provider }) => {
      void queryClient.invalidateQueries({ queryKey: ["provider-connection", provider] });
      void queryClient.invalidateQueries({ queryKey: ["activities"] });
    },
  });
}

export function useUpdateProviderConnection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ provider, syncSince }: { provider: string; syncSince: string | null }) =>
      apiRequest<ProviderConnectionView>(`/api/v1/providers/${provider}/connection`, {
        method: "PATCH",
        json: { sync_since: syncSince },
      }),
    onSuccess: (_data, { provider }) => {
      void queryClient.invalidateQueries({ queryKey: ["provider-connection", provider] });
    },
  });
}

export function useProviderConfig(provider: string) {
  return useQuery({
    queryKey: ["provider-config", provider],
    queryFn: () => apiRequest<ClientConfigView>(`/api/v1/providers/${provider}/client/config`),
  });
}

export type ProviderConfigInput = {
  client_id: string;
  /** Blank = keep the stored secret (it can never be read back). */
  client_secret: string;
  display_name: string;
};

export function useSaveProviderConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ provider, input }: { provider: string; input: ProviderConfigInput }) =>
      apiRequest<ClientConfigView>(`/api/v1/providers/${provider}/client/config`, {
        method: "PUT",
        json: {
          client_id: input.client_id,
          client_secret: input.client_secret === "" ? null : input.client_secret,
          display_name: input.display_name === "" ? null : input.display_name,
        },
      }),
    onSuccess: (_data, { provider }) => {
      void queryClient.invalidateQueries({ queryKey: ["provider-config", provider] });
      // The configured flag on /providers changed: refresh the list too.
      void queryClient.invalidateQueries({ queryKey: ["providers"] });
    },
  });
}

export function useDeleteProviderConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (provider: string) =>
      apiRequest<void>(`/api/v1/providers/${provider}/client/config`, { method: "DELETE" }),
    onSuccess: (_data, provider) => {
      void queryClient.invalidateQueries({ queryKey: ["provider-config", provider] });
      void queryClient.invalidateQueries({ queryKey: ["providers"] });
    },
  });
}
