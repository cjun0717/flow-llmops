<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: 'sm' | 'md' | 'lg'
  }>(),
  { size: 'md' },
)
</script>

<template>
  <div class="flex items-center min-w-0" :class="size === 'lg' ? 'gap-3' : 'gap-2.5'">
    <div
      class="flex-shrink-0 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-700 text-white font-bold flex items-center justify-center shadow-sm"
      :class="{
        'w-7 h-7 text-xs': size === 'sm',
        'w-8 h-8 text-sm': size === 'md',
        'w-10 h-10 text-base': size === 'lg',
      }"
    >
      F
    </div>
    <div class="flex flex-col min-w-0" :class="size === 'lg' ? 'leading-tight' : 'leading-none'">
      <span
        class="font-bold text-gray-900 tracking-tight"
        :class="{
          'text-sm': size === 'sm',
          'text-[15px]': size === 'md',
          'text-2xl': size === 'lg',
        }"
      >
        Flow
      </span>
      <span
        class="font-medium text-gray-400 tracking-[0.18em]"
        :class="{
          'text-[10px] mt-0.5': size === 'sm' || size === 'md',
          'text-xs mt-1 tracking-[0.22em]': size === 'lg',
        }"
      >
        LLMOps
      </span>
    </div>
  </div>
</template>
