import { useMemoryDetail, useMemoryRelated } from "@ynara/core/features/memory";
import { MemoryLayerSchema } from "@ynara/shared-schemas";
import { useRouter } from "expo-router";
import { type ReactNode, useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Text } from "@/components/ui/Text";
import { ApiError } from "@/lib/api";
import { MemoryDetailActions } from "./components/MemoryDetailActions";
import { MemoryDetailSkeleton } from "./components/MemoryDetailSkeleton";
import { MemoryDetailView } from "./components/MemoryDetailView";

/** Estado terminal (capa inválida / 404 / error): un card simple. */
function NotFound({ title, hint }: { title: string; hint: string }) {
  return (
    <View className="gap-1 rounded-lg border border-border bg-bg p-4">
      <Text className="text-body text-ink">{title}</Text>
      <Text className="text-body-sm text-ink-soft">{hint}</Text>
    </View>
  );
}

/**
 * Dispatcher del detalle de memoria (espejo del `MemoryDetailRoute` de web).
 * Valida la capa (llega por query `?capa=`), pide el detalle + relacionados, y
 * resuelve los estados: capa inválida / 404 / error / cargando / detalle. El
 * back y el shell (SafeAreaView + scroll) son comunes a todos los estados.
 */
export function MemoryDetailScreen({
  memoryRef,
  rawLayer,
}: {
  memoryRef: string;
  rawLayer: string | undefined;
}) {
  const router = useRouter();
  const parsed = MemoryLayerSchema.safeParse(rawLayer);
  const [now] = useState(() => new Date());

  // Hooks siempre se llaman; con capa inválida se usa una centinela que igual
  // no se muestra (se corta antes con el NotFound).
  const layer = parsed.success ? parsed.data : "semantic";
  const detail = useMemoryDetail(layer, memoryRef);
  const related = useMemoryRelated(layer, detail.data);

  let content: ReactNode;
  if (!parsed.success) {
    content = (
      <NotFound
        title="Este enlace no es válido"
        hint="No sabemos de qué tipo de recuerdo se trata. Volvé y entrá de nuevo."
      />
    );
  } else if (detail.isPending) {
    content = <MemoryDetailSkeleton />;
  } else if (detail.isError) {
    content =
      detail.error instanceof ApiError && detail.error.status === 404 ? (
        <NotFound
          title="No encontramos este recuerdo"
          hint="Puede que se haya borrado. Volvé a la lista para ver lo que hay."
        />
      ) : (
        <NotFound
          title="No pudimos abrir este recuerdo"
          hint="Puede ser un problema de conexión. Volvé e intentá de nuevo."
        />
      );
  } else {
    content = (
      <MemoryDetailView
        layer={layer}
        item={detail.data}
        related={related.data ?? []}
        relatedPending={related.isPending}
        now={now}
        actions={<MemoryDetailActions layer={layer} item={detail.data} />}
      />
    );
  }

  return (
    <SafeAreaView className="flex-1 bg-bg-canvas" edges={["top"]}>
      <ScrollView contentContainerClassName="gap-6 px-6 py-6">
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Volver a Memoria"
          hitSlop={8}
          onPress={() => router.back()}
          className="self-start"
        >
          <Text className="text-button text-ink-soft">‹ Memoria</Text>
        </Pressable>
        {content}
      </ScrollView>
    </SafeAreaView>
  );
}
