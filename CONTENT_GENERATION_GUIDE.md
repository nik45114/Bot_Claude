# 🎨 AI Content Generation Guide

## Overview

Club Assistant Bot now includes advanced AI content generation capabilities with automatic content type detection. The system can generate text, images, and (soon) videos based on user requests.

## Features

### 🤖 Auto-Detection
The bot automatically detects what type of content you want to generate:
- **Text** - Articles, posts, descriptions, stories
- **Images** - Illustrations, logos, artwork (DALL-E 3)
- **Video** - Animations and videos (coming soon)

### 🎯 Models Used
- **Text Generation**: Active GPT model (configurable by admins)
  - gpt-4o-mini (default, fast and cost-effective)
  - gpt-4o (optimal balance)
  - gpt-4-turbo (advanced)
  - gpt-4 (best quality)
  - gpt-3.5-turbo (budget option)
- **Image Generation**: DALL-E 3 (1024x1024px)
- **Video Generation**: Coming soon (RunwayML, Pika Labs, Stable Video)

## Usage

### Basic Command
```
/generate <your description>
```

### Examples

#### Text Generation
```
/generate напиши статью про искусственный интеллект
/generate создай описание для кофейни
/generate сочини короткую историю про космос
```

#### Image Generation
```
/generate создай изображение футуристического города
/generate нарисуй логотип для кофейни
/generate изобрази закат на океане в стиле импрессионизма
```

#### Video Generation (Coming Soon)
```
/generate создай видео с анимацией логотипа
/generate сделай видеоролик про продукт
```

## Menu Navigation

Access content generation through the main menu:
1. Click 🎨 **Генерация контента**
2. Choose your content type:
   - ✍️ Генерация текста
   - 🎨 Генерация изображений
   - 🎬 Генерация видео
3. View generation history with 📜 **История генераций**

## Admin Features

### 🔧 GPT Model Switching

Admins can change the active GPT model:

1. Go to 🔧 **Админ-панель**
2. Click ⚙️ **Настройки GPT модели**
3. Select desired model:
   - ✅ GPT-4o Mini (быстрая) - Current default
   - GPT-4o (оптимальная) - Best balance
   - GPT-4 Turbo - Advanced features
   - GPT-4 (лучшее качество) - Highest quality
   - GPT-3.5 Turbo (бюджетная) - Cost-effective

### Model Comparison

| Model | Speed | Quality | Cost | Best For |
|-------|-------|---------|------|----------|
| GPT-4o Mini | ⚡⚡⚡ | ⭐⭐⭐ | 💰 | Simple tasks, fast responses |
| GPT-4o | ⚡⚡ | ⭐⭐⭐⭐ | 💰💰 | General use, recommended |
| GPT-4 Turbo | ⚡⚡ | ⭐⭐⭐⭐ | 💰💰💰 | Complex tasks |
| GPT-4 | ⚡ | ⭐⭐⭐⭐⭐ | 💰💰💰💰 | Highest quality content |
| GPT-3.5 Turbo | ⚡⚡⚡ | ⭐⭐ | 💰 | Budget option |

## Configuration

### config.json
```json
{
  "gpt_model": "gpt-4o-mini",
  "content_generation": {
    "enabled": true,
    "text_max_tokens": 1000,
    "image_model": "dall-e-3",
    "image_size": "1024x1024"
  }
}
```

## Database Schema

### content_generations Table
Stores all generation requests and results:
- `id` - Unique generation ID
- `user_id` - User who requested
- `request_text` - Original request
- `content_type` - text/image/video
- `generated_content` - Generated text
- `image_url` - URL for generated images
- `video_url` - URL for generated videos
- `model_used` - Model used for generation
- `status` - pending/processing/completed/failed
- `error_message` - Error details if failed
- `created_at` - Request timestamp
- `completed_at` - Completion timestamp

### gpt_settings Table
Stores active GPT model configuration:
- `id` - Always 1 (single row)
- `active_model` - Currently active model name
- `updated_by` - Admin who changed it
- `updated_at` - Last update timestamp

## Tips for Best Results

### Text Generation
- Be specific about the topic and style
- Specify desired length (short, medium, long)
- Mention target audience if relevant
- Include any key points to cover

### Image Generation
- Provide detailed descriptions
- Specify artistic style if desired
- Mention colors, mood, composition
- Be clear about subject and setting
- Generation takes ~30 seconds

### Video Generation (Coming Soon)
- Describe the scene or animation
- Specify duration if possible
- Mention any text overlays needed
- Describe desired mood/style

## Generation History

View your generation history:
1. Open 🎨 **Генерация контента** menu
2. Click 📜 **История генераций**
3. See last 10 generations with:
   - Content type icon
   - Status indicator
   - Request preview
   - Generation ID and timestamp

Status indicators:
- ✅ Completed
- ⏳ Processing
- ❌ Failed
- ⏸ Pending

## Troubleshooting

### "Ошибка генерации"
- Check your OpenAI API key in config.json
- Verify API key has sufficient credits
- Try a shorter/simpler prompt
- Check if content violates OpenAI policies

### Image Generation Slow
- DALL-E 3 typically takes 20-40 seconds
- This is normal, please be patient
- Complex images may take longer

### Model Change Not Working
- Only admins can change models
- Ensure you have admin privileges
- Check database permissions

## API Integration Details

### Text Generation
Uses OpenAI Chat Completions API:
- Temperature: 0.7 (creative but coherent)
- Max tokens: 1000 (configurable)
- System prompt: Creative AI assistant

### Image Generation
Uses OpenAI DALL-E 3 API:
- Quality: Standard
- Size: 1024x1024px
- Number of images: 1

### Video Generation (Planned)
Future integrations:
- **RunwayML Gen-2**: Text/image to video
- **Pika Labs**: AI video generation
- **Stable Video Diffusion**: Open-source option

## Security & Privacy

- All generations are logged to database
- User IDs are tracked for accountability
- Generated content is not shared between users
- API keys are securely stored in config.json
- Model changes require admin privileges

## Cost Considerations

💡 Tip: Start with gpt-4o-mini and upgrade only if needed.

For current pricing information, please refer to:
- OpenAI Pricing Page: https://openai.com/pricing
- Pricing may vary based on your OpenAI plan and usage volume
- Monitor your usage in the OpenAI dashboard to track costs

Relative cost comparison (from cheapest to most expensive):
1. **GPT-4o Mini** - Most cost-effective
2. **GPT-3.5 Turbo** - Budget option
3. **GPT-4o** - Balanced
4. **GPT-4 Turbo** - Advanced
5. **GPT-4** - Premium pricing
6. **DALL-E 3** - Per-image pricing

## Support

For issues or questions:
- Check bot logs: `sudo journalctl -u club_assistant -f`
- Review OpenAI API dashboard for quota/errors
- Contact bot administrator

---

**Version**: 4.11+
**Last Updated**: 2024
**Status**: ✅ Production Ready (Video generation coming soon)
