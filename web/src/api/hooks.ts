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

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { max_heart_rate: number | null; resting_heart_rate: number | null }) =>
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
    mutationFn: (provider: string) =>
      apiRequest<SyncResultView>(`/api/v1/providers/${provider}/sync`, { method: "POST" }),
    onSuccess: (_data, provider) => {
      void queryClient.invalidateQueries({ queryKey: ["provider-connection", provider] });
      void queryClient.invalidateQueries({ queryKey: ["activities"] });
    },
  });
}
