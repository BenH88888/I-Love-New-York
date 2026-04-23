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
  dims?: PlaceDim[];
}

export type QueryDimension= {
  dimension: number;
  activation: number;
  terms: string[];
}

export type BaseModel = 'tfidf' | 'sbert'

export interface PlaceDim {
  dimension: number;
  activation: number;
  terms: string[];
}