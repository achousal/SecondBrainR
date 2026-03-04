import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const docs = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "../docs/manual" }),
  schema: z.object({
    title: z.string().optional(),
    description: z.string().optional(),
    type: z.string().optional(),
    created: z.coerce.string().optional(),
  }),
});

export const collections = { docs };
