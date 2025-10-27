#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR Module - Модуль для извлечения чисел из фото смен
Использует Tesseract OCR для распознавания текста и чисел
"""

import logging
import cv2
import numpy as np
import re
import json
from typing import Dict, List, Optional, Tuple
from PIL import Image
import pytesseract
import os

logger = logging.getLogger(__name__)

class OCRProcessor:
    """Процессор OCR для извлечения чисел из фото"""
    
    def __init__(self, tesseract_path: str = None):
        self.tesseract_path = tesseract_path
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        
        # Настройки для лучшего распознавания чисел
        self.config = '--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789., '
        
        # Паттерны для поиска чисел в тексте
        self.number_patterns = {
            'fact_cash': [
                r'факт\s*нал[а-я]*\s*:?\s*(\d+(?:[.,]\d+)?)',
                r'нал[а-я]*\s*:?\s*(\d+(?:[.,]\d+)?)',
                r'наличные\s*:?\s*(\d+(?:[.,]\d+)?)',
                r'cash\s*:?\s*(\d+(?:[.,]\d+)?)'
            ],
            'fact_card': [
                r'факт\s*карт[а-я]*\s*:?\s*(\d+(?:[.,]\d+)?)',
                r'карт[а-я]*\s*:?\s*(\d+(?:[.,]\d+)?)',
                r'безнал[а-я]*\s*:?\s*(\d+(?:[.,]\d+)?)',
                r'card\s*:?\s*(\d+(?:[.,]\d+)?)'
            ],
            'qr_amount': [
                r'qr\s*:?\s*(\d+(?:[.,]\d+)?)',
                r'кью\s*ар\s*:?\s*(\d+(?:[.,]\d+)?)',
                r'qr\s*код\s*:?\s*(\d+(?:[.,]\d+)?)'
            ],
            'card2_amount': [
                r'карт[а-я]*\s*2\s*:?\s*(\d+(?:[.,]\d+)?)',
                r'вторая\s*карт[а-я]*\s*:?\s*(\d+(?:[.,]\d+)?)',
                r'card2\s*:?\s*(\d+(?:[.,]\d+)?)'
            ],
            'safe_cash_end': [
                r'сейф\s*:?\s*(\d+(?:[.,]\d+)?)',
                r'офиц[а-я]*\s*:?\s*(\d+(?:[.,]\d+)?)',
                r'safe\s*:?\s*(\d+(?:[.,]\d+)?)',
                r'касса\s*офиц[а-я]*\s*:?\s*(\d+(?:[.,]\d+)?)'
            ],
            'box_cash_end': [
                r'коробк[а-я]*\s*:?\s*(\d+(?:[.,]\d+)?)',
                r'box\s*:?\s*(\d+(?:[.,]\d+)?)',
                r'касса\s*коробк[а-я]*\s*:?\s*(\d+(?:[.,]\d+)?)'
            ]
        }
    
    def preprocess_image(self, image_path: str) -> np.ndarray:
        """Предобработка изображения для лучшего OCR"""
        try:
            # Загружаем изображение
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")
            
            # Конвертируем в серый
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Увеличиваем контраст
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Убираем шум
            denoised = cv2.medianBlur(enhanced, 3)
            
            # Применяем пороговую обработку
            _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Морфологические операции для улучшения текста
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            return processed
            
        except Exception as e:
            logger.error(f"❌ Error preprocessing image: {e}")
            return None
    
    def extract_text_from_image(self, image_path: str) -> Tuple[str, float]:
        """Извлечение текста из изображения с помощью Tesseract"""
        try:
            # Предобработка изображения
            processed_image = self.preprocess_image(image_path)
            if processed_image is None:
                return "", 0.0
            
            # OCR с разными настройками
            configs = [
                '--oem 3 --psm 6',  # Блок текста
                '--oem 3 --psm 8',  # Одно слово
                '--oem 3 --psm 7',  # Одна строка
                '--oem 3 --psm 13'  # Сырая строка
            ]
            
            best_text = ""
            best_confidence = 0.0
            
            for config in configs:
                try:
                    # Получаем текст и уверенность
                    data = pytesseract.image_to_data(processed_image, config=config, output_type=pytesseract.Output.DICT)
                    
                    # Собираем текст
                    text_parts = []
                    confidences = []
                    
                    for i in range(len(data['text'])):
                        if int(data['conf'][i]) > 30:  # Минимальная уверенность
                            text_parts.append(data['text'][i])
                            confidences.append(int(data['conf'][i]))
                    
                    text = ' '.join(text_parts)
                    avg_confidence = np.mean(confidences) if confidences else 0
                    
                    if avg_confidence > best_confidence:
                        best_text = text
                        best_confidence = avg_confidence
                        
                except Exception as e:
                    logger.warning(f"OCR config failed: {config} - {e}")
                    continue
            
            logger.info(f"✅ OCR extracted text: {len(best_text)} chars, confidence: {best_confidence:.1f}%")
            return best_text, best_confidence / 100.0
            
        except Exception as e:
            logger.error(f"❌ Error extracting text from image: {e}")
            return "", 0.0
    
    def extract_numbers_from_text(self, text: str) -> Dict[str, Optional[float]]:
        """Извлечение чисел из текста по паттернам"""
        try:
            extracted = {}
            text_lower = text.lower()
            
            for field, patterns in self.number_patterns.items():
                extracted[field] = None
                
                for pattern in patterns:
                    match = re.search(pattern, text_lower, re.IGNORECASE)
                    if match:
                        try:
                            # Преобразуем в число
                            number_str = match.group(1).replace(',', '.')
                            number = float(number_str)
                            
                            # Проверяем разумность числа (не больше 1 млн)
                            if 0 <= number <= 1000000:
                                extracted[field] = number
                                logger.info(f"✅ Extracted {field}: {number}")
                                break
                        except ValueError:
                            continue
            
            return extracted
            
        except Exception as e:
            logger.error(f"❌ Error extracting numbers from text: {e}")
            return {}
    
    def process_image(self, image_path: str) -> Dict:
        """Полная обработка изображения: OCR + извлечение чисел"""
        try:
            start_time = datetime.now()
            
            # Извлекаем текст
            text, confidence = self.extract_text_from_image(image_path)
            
            # Извлекаем числа
            numbers = self.extract_numbers_from_text(text)
            
            # Подсчитываем количество найденных чисел
            found_count = sum(1 for v in numbers.values() if v is not None)
            total_fields = len(numbers)
            completion_rate = found_count / total_fields if total_fields > 0 else 0
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = {
                'raw_text': text,
                'confidence': confidence,
                'numbers': numbers,
                'found_count': found_count,
                'total_fields': total_fields,
                'completion_rate': completion_rate,
                'processing_time': processing_time,
                'success': confidence > 0.3 and found_count > 0
            }
            
            logger.info(f"✅ OCR processing completed: {found_count}/{total_fields} numbers found, "
                       f"confidence: {confidence:.1%}, time: {processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error processing image: {e}")
            return {
                'raw_text': '',
                'confidence': 0.0,
                'numbers': {},
                'found_count': 0,
                'total_fields': len(self.number_patterns),
                'completion_rate': 0.0,
                'processing_time': 0.0,
                'success': False,
                'error': str(e)
            }
    
    def compare_with_manual_data(self, ocr_numbers: Dict, manual_data: Dict) -> Dict:
        """Сравнение OCR данных с введенными вручную"""
        try:
            comparison = {}
            total_difference = 0
            matched_fields = 0
            
            for field in self.number_patterns.keys():
                ocr_value = ocr_numbers.get(field)
                manual_value = manual_data.get(field, 0)
                
                if ocr_value is not None and manual_value is not None:
                    difference = abs(ocr_value - manual_value)
                    percentage_diff = (difference / manual_value * 100) if manual_value > 0 else 0
                    
                    comparison[field] = {
                        'ocr_value': ocr_value,
                        'manual_value': manual_value,
                        'difference': difference,
                        'percentage_diff': percentage_diff,
                        'match': difference <= 100  # Разница не больше 100 рублей
                    }
                    
                    if comparison[field]['match']:
                        matched_fields += 1
                    
                    total_difference += difference
                else:
                    comparison[field] = {
                        'ocr_value': ocr_value,
                        'manual_value': manual_value,
                        'difference': None,
                        'percentage_diff': None,
                        'match': False
                    }
            
            # Общая оценка
            total_fields = len(self.number_patterns)
            match_rate = matched_fields / total_fields if total_fields > 0 else 0
            
            result = {
                'comparison': comparison,
                'matched_fields': matched_fields,
                'total_fields': total_fields,
                'match_rate': match_rate,
                'total_difference': total_difference,
                'overall_match': match_rate >= 0.7  # 70% полей должны совпадать
            }
            
            logger.info(f"✅ OCR comparison completed: {matched_fields}/{total_fields} fields match, "
                       f"match rate: {match_rate:.1%}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error comparing OCR with manual data: {e}")
            return {
                'comparison': {},
                'matched_fields': 0,
                'total_fields': len(self.number_patterns),
                'match_rate': 0.0,
                'total_difference': 0,
                'overall_match': False,
                'error': str(e)
            }
    
    def get_ocr_summary(self, ocr_result: Dict) -> str:
        """Получить текстовое резюме результатов OCR"""
        try:
            if not ocr_result.get('success', False):
                return "❌ OCR не смог обработать изображение"
            
            text = f"🔍 **Результаты OCR**\n\n"
            text += f"📊 **Общая статистика:**\n"
            text += f"  • Уверенность: {ocr_result['confidence']:.1%}\n"
            text += f"  • Найдено чисел: {ocr_result['found_count']}/{ocr_result['total_fields']}\n"
            text += f"  • Заполненность: {ocr_result['completion_rate']:.1%}\n"
            text += f"  • Время обработки: {ocr_result['processing_time']:.2f}с\n\n"
            
            text += f"💰 **Извлеченные суммы:**\n"
            numbers = ocr_result.get('numbers', {})
            
            field_names = {
                'fact_cash': 'Наличные',
                'fact_card': 'Карта',
                'qr_amount': 'QR',
                'card2_amount': 'Карта 2',
                'safe_cash_end': 'Сейф',
                'box_cash_end': 'Коробка'
            }
            
            for field, name in field_names.items():
                value = numbers.get(field)
                if value is not None:
                    text += f"  • {name}: {value:,.0f} ₽\n"
                else:
                    text += f"  • {name}: ❌ Не найдено\n"
            
            return text
            
        except Exception as e:
            logger.error(f"❌ Error creating OCR summary: {e}")
            return "❌ Ошибка при создании резюме OCR"


class OCRCommands:
    """Команды для работы с OCR"""
    
    def __init__(self, ocr_processor: OCRProcessor):
        self.ocr_processor = ocr_processor
    
    async def process_shift_photo(self, update, context, photo_path: str, shift_data: Dict = None) -> Dict:
        """Обработка фото смены с OCR"""
        try:
            await update.message.reply_text("🔍 Обрабатываю фото с помощью OCR...")
            
            # Обрабатываем изображение
            ocr_result = self.ocr_processor.process_image(photo_path)
            
            if not ocr_result.get('success', False):
                await update.message.reply_text(
                    "❌ Не удалось обработать фото.\n"
                    "Попробуйте сделать фото с лучшим освещением и четкостью."
                )
                return ocr_result
            
            # Показываем результаты
            summary = self.ocr_processor.get_ocr_summary(ocr_result)
            await update.message.reply_text(summary, parse_mode='Markdown')
            
            # Если есть данные для сравнения
            if shift_data:
                comparison = self.ocr_processor.compare_with_manual_data(
                    ocr_result['numbers'], shift_data
                )
                
                if comparison['overall_match']:
                    await update.message.reply_text(
                        f"✅ **OCR данные совпадают с введенными!**\n"
                        f"Совпадений: {comparison['matched_fields']}/{comparison['total_fields']} "
                        f"({comparison['match_rate']:.1%})"
                    )
                else:
                    await update.message.reply_text(
                        f"⚠️ **Обнаружены расхождения в данных**\n"
                        f"Совпадений: {comparison['matched_fields']}/{comparison['total_fields']} "
                        f"({comparison['match_rate']:.1%})\n"
                        f"Проверьте введенные данные."
                    )
            
            return ocr_result
            
        except Exception as e:
            logger.error(f"❌ Error processing shift photo: {e}")
            await update.message.reply_text(f"❌ Ошибка при обработке фото: {e}")
            return {'success': False, 'error': str(e)}
