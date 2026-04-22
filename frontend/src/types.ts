export interface Place {
  id: number;
  name: string;
  description: string;
  rating: number;
  price_level: string;
  formatted_address: string;
  website_url: string;
  latitude: number;
  longitude: number;
  reviews_text_combined: string;
  similarity_score: number | null;
  tags: string[];
}

export type QueryDimension= {
  dimension: number;
  activation: number;
  terms: string[];
}

export type BaseModel = 'tfidf' | 'sbert'